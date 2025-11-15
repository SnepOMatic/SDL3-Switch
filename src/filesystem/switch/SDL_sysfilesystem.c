/*
  Simple DirectMedia Layer
  Copyright (C) 1997-2020 Sam Lantinga <slouken@libsdl.org>

  This software is provided 'as-is', without any express or implied
  warranty.  In no event will the authors be held liable for any damages
  arising from the use of this software.

  Permission is granted to anyone to use this software for any purpose,
  including commercial applications, and to alter it and redistribute it
  freely, subject to the following restrictions:

  1. The origin of this software must not be misrepresented; you must not
     claim that you wrote the original software. If you use this software
     in a product, an acknowledgment in the product documentation would be
     appreciated but is not required.
  2. Altered source versions must be plainly marked as such, and must not be
     misrepresented as being the original software.
  3. This notice may not be removed or altered from any source distribution.
*/
#include "SDL_internal.h"

#ifdef SDL_FILESYSTEM_SWITCH

/* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * */
/* System dependent filesystem routines                                */

#include <limits.h>
#include <sys/unistd.h>
#include <sys/stat.h>
#include <errno.h>


char *SDL_SYS_GetBasePath(void)
{
    char *base_path = SDL_strdup("romfs:/");
    return base_path;
}

char *SDL_SYS_GetPrefPath(const char *org, const char *app)
{
    char *ret = NULL;
    char buf[PATH_MAX];
    size_t len;

    if (getcwd(buf, PATH_MAX)) {
        len = strlen(buf) + 2;
        ret = (char *)SDL_malloc(len);
        if (!ret) {
            SDL_OutOfMemory();
            return NULL;
        }
        SDL_snprintf(ret, len, "%s/", buf);
        return ret;
    }

    return NULL;
}

char *SDL_SYS_GetUserFolder(SDL_Folder folder)
{
    SDL_Unsupported();
    return NULL;
}

bool SDL_SYS_GetPathInfou(const char *path, SDL_PathInfo *info)
{
    SDL_PathInfo tmp_info;
	struct stat statbuf;
	const int rc = stat(path, &statbuf);

	if (rc < 0) {
		return SDL_SetError("Can't stat: %s", strerror(errno));
	}
	else if (S_ISREG(statbuf.st_mode)) {
		tmp_info.type = SDL_PATHTYPE_FILE;
		tmp_info.size = (Uint64) statbuf.st_size;
	}
	else if (S_ISDIR(statbuf.st_mode)) {
		tmp_info.type = SDL_PATHTYPE_DIRECTORY;
		tmp_info.size = 0;
	}
	else {
		tmp_info.type = SDL_PATHTYPE_OTHER;
		tmp_info.size = (Uint64) statbuf.st_size;
	}

	tmp_info.create_time = (SDL_Time) SDL_SECONDS_TO_NS(statbuf.st_ctime);
	tmp_info.modify_time = (SDL_Time) SDL_SECONDS_TO_NS(statbuf.st_mtime);
	tmp_info.access_time = (SDL_Time) SDL_SECONDS_TO_NS(statbuf.st_atime);

	if (info) {
		*info = tmp_info;
	}

	return true;
}

#endif /* SDL_FILESYSTEM_SWITCH */

/* vi: set ts=4 sw=4 expandtab: */
