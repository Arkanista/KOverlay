// Copyright 2021 The Mumble Developers. All rights reserved.
// Use of this source code is governed by a BSD-style license.

#ifndef MUMBLE_PLUGIN_API_H_
#define MUMBLE_PLUGIN_API_H_

#include "PluginComponents.h"

#define MUMBLE_PLUGIN_API_MAJOR_MACRO 1
#define MUMBLE_PLUGIN_API_MINOR_MACRO 0
#define MUMBLE_PLUGIN_API_PATCH_MACRO 0

#ifdef __cplusplus
extern "C" {
#endif

struct MumbleAPI_v_1_0_x {
	// Memory management
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *freeMemory)(mumble_plugin_id_t callerID, const void *pointer);

	// Getters
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *getActiveServerConnection)(mumble_plugin_id_t callerID, mumble_connection_t *connection);
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *isConnectionSynchronized)(mumble_plugin_id_t callerID, mumble_connection_t connection, bool *synchronized);
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *getLocalUserID)(mumble_plugin_id_t callerID, mumble_connection_t connection, mumble_userid_t *userID);
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *getUserName)(mumble_plugin_id_t callerID, mumble_connection_t connection, mumble_userid_t userID, const char **name);
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *getChannelName)(mumble_plugin_id_t callerID, mumble_connection_t connection, mumble_channelid_t channelID, const char **name);
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *getAllUsers)(mumble_plugin_id_t callerID, mumble_connection_t connection, mumble_userid_t **userIDs, size_t *userCount);
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *getAllChannels)(mumble_plugin_id_t callerID, mumble_connection_t connection, mumble_channelid_t **channelIDs, size_t *channelCount);
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *getChannelOfUser)(mumble_plugin_id_t callerID, mumble_connection_t connection, mumble_userid_t userID, mumble_channelid_t *channelID);
	mumble_error_t (MUMBLE_PLUGIN_CALLING_CONVENTION *getUsersInChannel)(mumble_plugin_id_t callerID, mumble_connection_t connection, mumble_channelid_t channelID, mumble_userid_t **userIDs, size_t *userCount);
};

#define MUMBLE_API_CAST(ptrName) (*((struct MumbleAPI_v_1_0_x *) (ptrName)))

#ifdef __cplusplus
}
#endif

#endif // MUMBLE_PLUGIN_API_H_
