################################################################################
# OpenHD
#
# Licensed under the GNU General Public License (GPL) Version 3.
#
# This software is provided "as-is," without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose, and non-infringement. For details, see the
# full license in the LICENSE file provided with this source code.
#
# Non-Military Use Only:
# This software and its associated components are explicitly intended for
# civilian and non-military purposes. Use in any military or defense
# applications is strictly prohibited unless explicitly and individually
# licensed otherwise by the OpenHD Team.
#
# Contributors:
# A full list of contributors can be found at the OpenHD GitHub repository:
# https://github.com/OpenHD
#
# © OpenHD, All Rights Reserved.
################################################################################

$(info Building the OpenHD package...)

# Git repository
OPENHD_UPSTREAM_SITE = https://github.com/OpenHD/OpenHD.git

ifeq ($(OPENHD_LOCAL_SITE),)
OPENHD_SITE = $(OPENHD_UPSTREAM_SITE)
OPENHD_SITE_METHOD = git
OPENHD_GIT_SUBMODULES = YES

# Always resolve to the current HEAD of the openhd-3.0 branch
# Note: this is not reproducible and is not the recommended Buildroot approach.
OPENHD_VERSION = $(shell git ls-remote $(OPENHD_SITE) refs/heads/openhd-3.0 | cut -f1)
else
OPENHD_SITE = $(OPENHD_LOCAL_SITE)
OPENHD_SITE_METHOD = local
OPENHD_VERSION = local
endif

# openhd-3.0 keeps the CMake project in the OpenHD/ subdirectory.
OPENHD_SUBDIR = OpenHD

# Install to the target system
OPENHD_INSTALL_TARGET = YES

# Dependencies
OPENHD_DEPENDENCIES = poco libsodium gstreamer1 gst1-plugins-base libpcap host-pkgconf

# CMake options
OPENHD_CONF_OPTS = \
    -DENABLE_USB_CAMERAS=OFF \
    -DCMAKE_EXE_LINKER_FLAGS="-lstdc++fs"

define OPENHD_INSTALL_TARGET_CMDS
	$(info OpenHD Build Directory: $(@D))
	$(INSTALL) -D -m 0755 $(@D)/openhd $(TARGET_DIR)/usr/bin/openhd
	$(INSTALL) -D -m 0755 $(BR2_EXTERNAL_YOURTREE_PATH)/package/OpenHD/start.sh \
		$(TARGET_DIR)/etc/init.d/S99openhd
endef

$(eval $(cmake-package))
