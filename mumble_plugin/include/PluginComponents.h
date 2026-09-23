// Copyright 2021 The Mumble Developers. All rights reserved.
// Use of this source code is governed by a BSD-style license.

#ifndef MUMBLE_PLUGIN_COMPONENTS_H_
#define MUMBLE_PLUGIN_COMPONENTS_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#if defined(_MSC_VER)
#	define MUMBLE_PLUGIN_CALLING_CONVENTION __cdecl
#elif defined(__MINGW32__)
#	define MUMBLE_PLUGIN_CALLING_CONVENTION __attribute__((cdecl))
#else
#	define MUMBLE_PLUGIN_CALLING_CONVENTION
#endif

#if defined(__GNUC__) && !defined(__MINGW32__)
#	define MUMBLE_PLUGIN_EXPORT __attribute__((visibility("default")))
#elif defined(_MSC_VER)
#	define MUMBLE_PLUGIN_EXPORT __declspec(dllexport)
#elif defined(__MINGW32__)
#	define MUMBLE_PLUGIN_EXPORT __attribute__((dllexport))
#else
#	define MUMBLE_PLUGIN_EXPORT
#endif

#ifdef __cplusplus
extern "C" {
#endif

enum Mumble_PluginFeature {
	MUMBLE_FEATURE_NONE = 0,
	MUMBLE_FEATURE_POSITIONAL = 1 << 0,
	MUMBLE_FEATURE_AUDIO = 1 << 1
};

enum Mumble_TalkingState {
	MUMBLE_TS_INVALID = -1,
	MUMBLE_TS_PASSIVE = 0,
	MUMBLE_TS_TALKING,
	MUMBLE_TS_WHISPERING,
	MUMBLE_TS_SHOUTING,
	MUMBLE_TS_TALKING_MUTED
};

enum Mumble_TransmissionMode {
	MUMBLE_TM_CONTINOUS,
	MUMBLE_TM_VOICE_ACTIVATION,
	MUMBLE_TM_PUSH_TO_TALK
};

enum Mumble_ErrorCode {
	MUMBLE_EC_INTERNAL_ERROR = -2,
	MUMBLE_EC_GENERIC_ERROR  = -1,
	MUMBLE_EC_OK             = 0,
	MUMBLE_EC_POINTER_NOT_FOUND,
	MUMBLE_EC_NO_ACTIVE_CONNECTION,
	MUMBLE_EC_USER_NOT_FOUND,
	MUMBLE_EC_CHANNEL_NOT_FOUND,
	MUMBLE_EC_CONNECTION_NOT_FOUND,
	MUMBLE_EC_UNKNOWN_TRANSMISSION_MODE,
	MUMBLE_EC_AUDIO_NOT_AVAILABLE,
	MUMBLE_EC_INVALID_SAMPLE,
	MUMBLE_EC_INVALID_PLUGIN_ID,
	MUMBLE_EC_INVALID_MUTE_TARGET,
	MUMBLE_EC_CONNECTION_UNSYNCHRONIZED,
	MUMBLE_EC_INVALID_API_VERSION,
	MUMBLE_EC_UNSYNCHRONIZED_BLOB,
	MUMBLE_EC_UNKNOWN_SETTINGS_KEY,
	MUMBLE_EC_WRONG_SETTINGS_TYPE,
	MUMBLE_EC_SETTING_WAS_REMOVED,
	MUMBLE_EC_DATA_TOO_BIG,
	MUMBLE_EC_DATA_ID_TOO_LONG
};

typedef enum Mumble_TalkingState mumble_talking_state_t;
typedef enum Mumble_TransmissionMode mumble_transmission_mode_t;
typedef int32_t mumble_connection_t;
typedef uint32_t mumble_userid_t;
typedef int32_t mumble_channelid_t;
typedef enum Mumble_ErrorCode mumble_error_t;
typedef uint32_t mumble_plugin_id_t;

struct MumbleVersion {
	int32_t major;
	int32_t minor;
	int32_t patch;
};

typedef struct MumbleVersion mumble_version_t;

struct MumbleStringWrapper {
	const char *data;
	size_t size;
	bool needsReleasing;
};

#define MUMBLE_STATUS_OK MUMBLE_EC_OK

#ifdef __cplusplus
}
#endif

#endif // MUMBLE_PLUGIN_COMPONENTS_H_
