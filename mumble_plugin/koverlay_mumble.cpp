#include "MumblePlugin.h"

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <cstring>
#include <algorithm>
#include <set>
#include <cerrno>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
typedef int socklen_t;
typedef intptr_t ssize_t;
#define close closesocket
#define poll WSAPoll
#define MSG_NOSIGNAL 0
#define GET_SOCKET_ERROR() WSAGetLastError()
#define IS_WOULDBLOCK(err) ((err) == WSAEWOULDBLOCK)
#define IS_INTR(err) ((err) == WSAEINTR)
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#define GET_SOCKET_ERROR() errno
#define IS_WOULDBLOCK(err) ((err) == EAGAIN || (err) == EWOULDBLOCK)
#define IS_INTR(err) ((err) == EINTR)
#endif

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

// Mutex protecting Mumble state (users, channel, active connection)
std::mutex g_stateMutex;
std::condition_variable g_stateCv;
bool g_stateDirty = false;
uint64_t g_stateSeq = 0;

mumble_connection_t g_activeConnection = -1;
mumble_channelid_t g_localChannel = -1;
mumble_userid_t g_localUserID = 0;
std::map<mumble_userid_t, UserInfo> g_users;

// Mutex protecting IPC client sockets
std::mutex g_clientsMutex;
int g_serverSocket = -1;
std::vector<int> g_clients;

std::thread g_serverThread;
std::thread g_broadcastThread;

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

            // If username is unknown, empty, or fallback/placeholder, never include it in the overlay
            if (u.name.empty()) {
                continue;
            }
            if (u.name.rfind("User_", 0) == 0 || u.name.rfind("user_", 0) == 0) {
                bool onlyDigits = true;
                for (size_t i = 5; i < u.name.size(); ++i) {
                    if (!std::isdigit(static_cast<unsigned char>(u.name[i]))) {
                        onlyDigits = false;
                        break;
                    }
                }
                if (onlyDigits && u.name.size() > 5) {
                    continue;
                }
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
        ssize_t sent = send(fd, data.data() + total, static_cast<int>(data.size() - total), MSG_NOSIGNAL);
        if (sent > 0) {
            total += sent;
        } else if (sent < 0) {
            int err = GET_SOCKET_ERROR();
            if (IS_WOULDBLOCK(err)) {
                // Socket buffer momentarily full, wait up to 10ms for it to become writable
                pollfd pfd{};
                pfd.fd = fd;
                pfd.events = POLLOUT;
                int pret = poll(&pfd, 1, 10);
                if (pret > 0 && (pfd.revents & POLLOUT)) {
                    continue;
                }
            } else if (IS_INTR(err)) {
                continue;
            }
            return false;
        } else {
            return false;
        }
    }
    return true;
}

void notifyStateChangedLocked() {
    g_stateDirty = true;
    ++g_stateSeq;
    g_stateCv.notify_one();
}

void broadcastMessage(const std::string &msg) {
    std::vector<int> aliveClients;
    std::lock_guard<std::mutex> lock(g_clientsMutex);

    for (int fd : g_clients) {
        if (sendAll(fd, msg)) {
            aliveClients.push_back(fd);
        } else {
            close(fd);
        }
    }
    g_clients = std::move(aliveClients);
}

void broadcastWorkerLoop() {
    uint64_t lastSeq = 0;

    while (g_running) {
        std::string msg;
        {
            std::unique_lock<std::mutex> lock(g_stateMutex);
            g_stateCv.wait(lock, [] {
                return !g_running || g_stateDirty;
            });

            if (!g_running) {
                break;
            }

            g_stateDirty = false;
            if (g_stateSeq == lastSeq) {
                continue;
            }
            lastSeq = g_stateSeq;

            msg = buildStateJsonLocked();
        }

        // Broadcast to clients OUTSIDE g_stateMutex so Mumble callbacks are never blocked!
        broadcastMessage(msg);
    }
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
    auto &info = g_users[userID];
    if (g_mumbleAPI.getUserName && g_mumbleAPI.getUserName(g_pluginID, connection, userID, &namePtr) == MUMBLE_STATUS_OK && namePtr) {
        if (namePtr[0] != '\0') {
            info.name = namePtr;
        }
        if (g_mumbleAPI.freeMemory) {
            g_mumbleAPI.freeMemory(g_pluginID, namePtr);
        }
    }
    // Never fallback to "User_" + userID. If the name is unknown, leave it empty
    // so the overlay silently ignores it until a valid name is resolved.

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
    setsockopt(serverFd, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char *>(&opt), sizeof(opt));

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
        std::lock_guard<std::mutex> lock(g_clientsMutex);
        g_serverSocket = serverFd;
    }

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
                // Set non-blocking mode on client socket
#ifdef _WIN32
                u_long mode = 1;
                ioctlsocket(clientFd, FIONBIO, &mode);
#else
                int flags = fcntl(clientFd, F_GETFL, 0);
                if (flags != -1) {
                    fcntl(clientFd, F_SETFL, flags | O_NONBLOCK);
                }
#endif

                {
                    std::lock_guard<std::mutex> lock(g_clientsMutex);
                    g_clients.push_back(clientFd);
                }

                // Immediately trigger broadcast worker to send state snapshot to the new client
                {
                    std::lock_guard<std::mutex> lock(g_stateMutex);
                    notifyStateChangedLocked();
                }
            }
        }
    }

    // Cleanup server socket
    {
        std::lock_guard<std::mutex> lock(g_clientsMutex);
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
#ifdef _WIN32
    WSADATA wsaData;
    WSAStartup(MAKEWORD(2, 2), &wsaData);
#endif
    g_pluginID = id;
    g_running = true;
    g_stateDirty = false;
    g_stateSeq = 0;

    try {
        g_serverThread = std::thread(ipcServerLoop);
        g_broadcastThread = std::thread(broadcastWorkerLoop);
    } catch (...) {
        return MUMBLE_EC_GENERIC_ERROR;
    }

    return MUMBLE_STATUS_OK;
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_shutdown() {
    g_running = false;
    g_stateCv.notify_all();

    if (g_broadcastThread.joinable()) {
        g_broadcastThread.join();
    }
    if (g_serverThread.joinable()) {
        g_serverThread.join();
    }

    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        g_users.clear();
        g_localChannel = -1;
        g_activeConnection = -1;
    }

    {
        std::lock_guard<std::mutex> lock(g_clientsMutex);
        for (int fd : g_clients) {
            close(fd);
        }
        g_clients.clear();
    }
#ifdef _WIN32
    WSACleanup();
#endif
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
    bool isTalking = (talkingState == MUMBLE_TS_TALKING ||
                      talkingState == MUMBLE_TS_WHISPERING ||
                      talkingState == MUMBLE_TS_SHOUTING);

    std::lock_guard<std::mutex> lock(g_stateMutex);
    auto it = g_users.find(userID);
    if (it != g_users.end()) {
        if (it->second.talking != isTalking) {
            it->second.talking = isTalking;
            notifyStateChangedLocked();
        }
    } else {
        updateUserLocked(connection, userID);
        g_users[userID].talking = isTalking;
        notifyStateChangedLocked();
    }
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onUserAdded(
    mumble_connection_t connection, mumble_userid_t userID) {
    std::lock_guard<std::mutex> lock(g_stateMutex);
    updateUserLocked(connection, userID);
    notifyStateChangedLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onUserRemoved(
    mumble_connection_t, mumble_userid_t userID) {
    std::lock_guard<std::mutex> lock(g_stateMutex);
    g_users.erase(userID);
    notifyStateChangedLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onServerConnected(mumble_connection_t connection) {
    std::lock_guard<std::mutex> lock(g_stateMutex);
    syncAllUsersLocked(connection);
    notifyStateChangedLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onServerDisconnected(mumble_connection_t) {
    std::lock_guard<std::mutex> lock(g_stateMutex);
    g_activeConnection = -1;
    g_localChannel = -1;
    g_users.clear();
    notifyStateChangedLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onServerSynchronized(mumble_connection_t connection) {
    std::lock_guard<std::mutex> lock(g_stateMutex);
    syncAllUsersLocked(connection);
    notifyStateChangedLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onChannelEntered(
    mumble_connection_t connection, mumble_userid_t userID, mumble_channelid_t, mumble_channelid_t newChannelID) {
    std::lock_guard<std::mutex> lock(g_stateMutex);
    if (userID == g_localUserID) {
        g_localChannel = newChannelID;
        syncAllUsersLocked(connection);
    }
    auto it = g_users.find(userID);
    if (it != g_users.end()) {
        it->second.channel_id = newChannelID;
    } else {
        updateUserLocked(connection, userID);
        g_users[userID].channel_id = newChannelID;
    }
    notifyStateChangedLocked();
}

MUMBLE_PLUGIN_EXPORT void MUMBLE_PLUGIN_CALLING_CONVENTION mumble_onChannelExited(
    mumble_connection_t, mumble_userid_t userID, mumble_channelid_t channelID) {
    std::lock_guard<std::mutex> lock(g_stateMutex);
    if (channelID != g_localChannel) {
        // Not our channel, ignore to avoid false updates
        return;
    }
    if (userID == g_localUserID) {
        g_localChannel = -1;
    }
    auto it = g_users.find(userID);
    if (it != g_users.end()) {
        it->second.channel_id = -1;
    }
    notifyStateChangedLocked();
}

} // extern "C"
