#include "MumblePlugin.h"

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <thread>
#include <mutex>
#include <atomic>
#include <cstring>
#include <algorithm>
#include <set>
#include <cerrno>

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>

namespace {

const int IPC_PORT = 25640;

struct UserInfo {
    std::string name;
    mumble_channelid_t channel_id = -1;
    bool talking = false;
};

std::atomic<bool> g_running{false};
mumble_plugin_id_t g_pluginID = 0;
struct MumbleAPI_v_1_0_x g_mumbleAPI;
bool g_hasAPI = false;

std::mutex g_mutex;
int g_serverSocket = -1;
std::vector<int> g_clients;
std::thread g_serverThread;

mumble_connection_t g_activeConnection = -1;
mumble_channelid_t g_localChannel = -1;
mumble_userid_t g_localUserID = 0;
std::map<mumble_userid_t, UserInfo> g_users;

std::string escapeJson(const std::string &input) {
    std::string output;
    output.reserve(input.size() + 8);
    for (char c : input) {
        if (c == '"') output += "\\\"";
        else if (c == '\\') output += "\\\\";
        else if (c == '\b') output += "\\b";
        else if (c == '\f') output += "\\f";
        else if (c == '\n') output += "\\n";
        else if (c == '\r') output += "\\r";
        else if (c == '\t') output += "\\t";
        else if (static_cast<unsigned char>(c) < 32) {
            char buf[8];
            snprintf(buf, sizeof(buf), "\\u%04x", static_cast<unsigned char>(c));
            output += buf;
        } else {
            output += c;
        }
    }
    return output;
}

std::string buildStateJsonLocked() {
    std::string json = "{\"type\":\"update\",\"channel_id\":";
    json += std::to_string(g_localChannel);
    json += ",\"clients\":[";

    // Strictly filter: only include users who belong to the local user's current channel
    if (g_localChannel != -1) {
        bool first = true;
        for (const auto &pair : g_users) {
            const UserInfo &u = pair.second;
            if (u.channel_id != g_localChannel) {
                continue;
            }

            if (!first) json += ",";
            first = false;

            json += "{\"name\":\"";
            json += escapeJson(u.name);
            json += "\",\"talking\":";
            json += (u.talking ? "true" : "false");
            json += "}";
        }
    }

    json += "]}\n";
    return json;
}

bool sendAll(int fd, const std::string &data) {
    size_t total = 0;
    while (total < data.size()) {
        ssize_t sent = send(fd, data.data() + total, data.size() - total, MSG_NOSIGNAL);
        if (sent > 0) {
            total += sent;
        } else if (sent < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
                usleep(1000);
                continue;
            }
            return false;
        } else {
            return false;
        }
    }
    return true;
}

void broadcastStateLocked() {
    std::string msg = buildStateJsonLocked();
    std::vector<int> aliveClients;

    for (int fd : g_clients) {
        if (sendAll(fd, msg)) {
            aliveClients.push_back(fd);
        } else {
            close(fd);
        }
    }
    g_clients = std::move(aliveClients);
}

void updateUserLocked(mumble_connection_t connection, mumble_userid_t userID) {
    if (!g_hasAPI) return;

    // Check local user ID
    mumble_userid_t localUID = 0;
    if (g_mumbleAPI.getLocalUserID && g_mumbleAPI.getLocalUserID(g_pluginID, connection, &localUID) == MUMBLE_STATUS_OK) {
        g_localUserID = localUID;
    }

    // Get user channel
    mumble_channelid_t cid = -1;
    if (g_mumbleAPI.getChannelOfUser && g_mumbleAPI.getChannelOfUser(g_pluginID, connection, userID, &cid) == MUMBLE_STATUS_OK) {
        if (userID == g_localUserID) {
            g_localChannel = cid;
        }
    }

    // Get user name
    const char *namePtr = nullptr;
    std::string name;
    if (g_mumbleAPI.getUserName && g_mumbleAPI.getUserName(g_pluginID, connection, userID, &namePtr) == MUMBLE_STATUS_OK && namePtr) {
        name = namePtr;
        if (g_mumbleAPI.freeMemory) {
            g_mumbleAPI.freeMemory(g_pluginID, namePtr);
        }
    } else {
        name = "User_" + std::to_string(userID);
    }

    auto &info = g_users[userID];
    info.name = name;
    info.channel_id = cid;
}

void syncAllUsersLocked(mumble_connection_t connection) {
    if (!g_hasAPI) return;
    g_activeConnection = connection;

    mumble_userid_t localUID = 0;
    if (g_mumbleAPI.getLocalUserID && g_mumbleAPI.getLocalUserID(g_pluginID, connection, &localUID) == MUMBLE_STATUS_OK) {
        g_localUserID = localUID;
        mumble_channelid_t cid = -1;
        if (g_mumbleAPI.getChannelOfUser && g_mumbleAPI.getChannelOfUser(g_pluginID, connection, localUID, &cid) == MUMBLE_STATUS_OK) {
            g_localChannel = cid;
        }
    }

    mumble_userid_t *users = nullptr;
    size_t count = 0;
    if (g_mumbleAPI.getAllUsers && g_mumbleAPI.getAllUsers(g_pluginID, connection, &users, &count) == MUMBLE_STATUS_OK && users) {
        std::set<mumble_userid_t> activeSet;
        for (size_t i = 0; i < count; ++i) {
            activeSet.insert(users[i]);
            updateUserLocked(connection, users[i]);
        }
        for (auto it = g_users.begin(); it != g_users.end(); ) {
            if (activeSet.find(it->first) == activeSet.end()) {
                it = g_users.erase(it);
            } else {
                ++it;
            }
        }
        if (g_mumbleAPI.freeMemory) {
            g_mumbleAPI.freeMemory(g_pluginID, users);
        }
    }
}

void ipcServerLoop() {
    int serverFd = socket(AF_INET, SOCK_STREAM, 0);
    if (serverFd < 0) {
        return;
    }

    int opt = 1;
    setsockopt(serverFd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    addr.sin_port = htons(IPC_PORT);

    if (bind(serverFd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) < 0) {
        close(serverFd);
        return;
    }

    if (listen(serverFd, 5) < 0) {
        close(serverFd);
        return;
    }

    {
        std::lock_guard<std::mutex> lock(g_mutex);
        g_serverSocket = serverFd;
    }

    int pollCount = 0;
    while (g_running) {
        pollfd pfd{};
        pfd.fd = serverFd;
        pfd.events = POLLIN;

        int ret = poll(&pfd, 1, 200); // 200ms timeout to check g_running
        if (ret > 0 && (pfd.revents & POLLIN)) {
            sockaddr_in clientAddr{};
            socklen_t clientLen = sizeof(clientAddr);
            int clientFd = accept(serverFd, reinterpret_cast<sockaddr *>(&clientAddr), &clientLen);
            if (clientFd >= 0) {
                // Set non-blocking or short timeout for safety
                std::lock_guard<std::mutex> lock(g_mutex);
                g_clients.push_back(clientFd);

                // Refresh user list if connected
                if (g_hasAPI) {
                    mumble_connection_t conn = -1;
                    if (g_mumbleAPI.getActiveServerConnection && g_mumbleAPI.getActiveServerConnection(g_pluginID, &conn) == MUMBLE_STATUS_OK && conn >= 0) {
                        syncAllUsersLocked(conn);
                    }
                }

                // Send immediate snapshot to newly connected client
                std::string snapshot = buildStateJsonLocked();
                send(clientFd, snapshot.c_str(), snapshot.size(), MSG_NOSIGNAL);
            }
        }

        // Periodic check every ~600ms if clients are connected
        pollCount++;
        if (pollCount >= 3) {
            pollCount = 0;
            std::lock_guard<std::mutex> lock(g_mutex);
            if (!g_clients.empty() && g_hasAPI) {
                mumble_connection_t conn = -1;
                if (g_mumbleAPI.getActiveServerConnection && g_mumbleAPI.getActiveServerConnection(g_pluginID, &conn) == MUMBLE_STATUS_OK && conn >= 0) {
                    mumble_channelid_t prevChannel = g_localChannel;
                    syncAllUsersLocked(conn);
                    if (prevChannel != g_localChannel) {
                        broadcastStateLocked();
                    }
                }
            }
        }
    }

    // Cleanup server and remaining clients
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        for (int fd : g_clients) {
            close(fd);
        }
        g_clients.clear();
        if (g_serverSocket >= 0) {
            close(g_serverSocket);
            g_serverSocket = -1;
        }
    }
}

} // namespace

// --------------------------------------------------------------------------------
// Exported Mumble Plugin API Functions
// --------------------------------------------------------------------------------

extern "C" {

MUMBLE_PLUGIN_EXPORT mumble_error_t MUMBLE_PLUGIN_CALLING_CONVENTION mumble_init(mumble_plugin_id_t id) {
    g_pluginID = id;
    g_running = true;

    try {
        g_serverThread = std::thread(ipcServerLoop);
    } catch (...) {
        return MUMBLE_EC_GENERIC_ERROR;
    }

    return MUMBLE_STATUS_OK;
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_shutdown() {
    g_running = false;
    if (g_serverThread.joinable()) {
        g_serverThread.join();
    }

    std::lock_guard<std::mutex> lock(g_mutex);
    g_users.clear();
    g_localChannel = -1;
    g_activeConnection = -1;
}

MUMBLE_PLUGIN_EXPORT struct MumbleStringWrapper MUMBLE_PLUGIN_CALLING_CONVENTION mumble_getName() {
    static const char name[] = "KOverlay Mumble Plugin";
    struct MumbleStringWrapper wrapper;
    wrapper.data = name;
    wrapper.size = sizeof(name) - 1;
    wrapper.needsReleasing = false;
    return wrapper;
}

MUMBLE_PLUGIN_EXPORT mumble_version_t MUMBLE_PLUGIN_CALLING_CONVENTION mumble_getAPIVersion() {
    return MUMBLE_PLUGIN_API_VERSION;
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_registerAPIFunctions(void *apiStruct) {
    if (apiStruct) {
        g_mumbleAPI = MUMBLE_API_CAST(apiStruct);
        g_hasAPI = true;
    }
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_releaseResource(const void *) {
    // We only return static strings, nothing needs releasing by Mumble
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_setMumbleInfo(mumble_version_t, mumble_version_t, mumble_version_t) {
}

MUMBLE_PLUGIN_EXPORT mumble_version_t MUMBLE_PLUGIN_CALLING_CONVENTION mumble_getVersion() {
    mumble_version_t ver = { 0, 1, 0 };
    return ver;
}

MUMBLE_PLUGIN_EXPORT struct MumbleStringWrapper MUMBLE_PLUGIN_CALLING_CONVENTION mumble_getAuthor() {
    static const char author[] = "Arkanis";
    struct MumbleStringWrapper wrapper;
    wrapper.data = author;
    wrapper.size = sizeof(author) - 1;
    wrapper.needsReleasing = false;
    return wrapper;
}

MUMBLE_PLUGIN_EXPORT struct MumbleStringWrapper MUMBLE_PLUGIN_CALLING_CONVENTION mumble_getDescription() {
    static const char desc[] = "KOverlay IPC bridge for Mumble voice and talking status.";
    struct MumbleStringWrapper wrapper;
    wrapper.data = desc;
    wrapper.size = sizeof(desc) - 1;
    wrapper.needsReleasing = false;
    return wrapper;
}

MUMBLE_PLUGIN_EXPORT uint32_t MUMBLE_PLUGIN_CALLING_CONVENTION mumble_getFeatures() {
    return MUMBLE_FEATURE_NONE;
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onUserTalkingStateChanged(
    mumble_connection_t connection, mumble_userid_t userID, mumble_talking_state_t talkingState) {
    std::lock_guard<std::mutex> lock(g_mutex);

    // Update talking status
    bool isTalking = (talkingState == MUMBLE_TS_TALKING ||
                      talkingState == MUMBLE_TS_WHISPERING ||
                      talkingState == MUMBLE_TS_SHOUTING);

    updateUserLocked(connection, userID);
    g_users[userID].talking = isTalking;

    broadcastStateLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onUserAdded(
    mumble_connection_t connection, mumble_userid_t userID) {
    std::lock_guard<std::mutex> lock(g_mutex);
    updateUserLocked(connection, userID);
    broadcastStateLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onUserRemoved(
    mumble_connection_t, mumble_userid_t userID) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_users.erase(userID);
    broadcastStateLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onServerConnected(mumble_connection_t connection) {
    std::lock_guard<std::mutex> lock(g_mutex);
    syncAllUsersLocked(connection);
    broadcastStateLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onServerDisconnected(mumble_connection_t) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_activeConnection = -1;
    g_localChannel = -1;
    g_users.clear();
    broadcastStateLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onServerSynchronized(mumble_connection_t connection) {
    std::lock_guard<std::mutex> lock(g_mutex);
    syncAllUsersLocked(connection);
    broadcastStateLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onChannelEntered(
    mumble_connection_t connection, mumble_userid_t userID, mumble_channelid_t, mumble_channelid_t newChannelID) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (userID == g_localUserID) {
        g_localChannel = newChannelID;
    }
    updateUserLocked(connection, userID);
    g_users[userID].channel_id = newChannelID;
    broadcastStateLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onChannelExited(
    mumble_connection_t connection, mumble_userid_t userID, mumble_channelid_t) {
    std::lock_guard<std::mutex> lock(g_mutex);
    updateUserLocked(connection, userID);
    broadcastStateLocked();
}

} // extern "C"
