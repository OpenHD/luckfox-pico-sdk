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

OPENHD_ARTOSYN_BUILD_DIR = $(ARTOSYN_SDK_ROOT)/host_drv/build-openhd-buildroot
OPENHD_ARTOSYN_CLIENT_LIB = $(OPENHD_ARTOSYN_BUILD_DIR)/app/ar8030/libar8030_client.a
OPENHD_ARTOSYN_COM_LIB = $(OPENHD_ARTOSYN_BUILD_DIR)/com/libcom.a

# CMake options
OPENHD_CONF_OPTS = \
    -DENABLE_USB_CAMERAS=OFF \
    -DCMAKE_EXE_LINKER_FLAGS="-lstdc++fs"

ifneq ($(ARTOSYN_SDK_ROOT),)
OPENHD_CONF_OPTS += -DARTOSYN_SDK_ROOT="$(ARTOSYN_SDK_ROOT)"
endif

ifneq ($(ARTOSYN_SDK_LIB),)
OPENHD_CONF_OPTS += -DARTOSYN_SDK_LIB="$(ARTOSYN_SDK_LIB)"
else ifneq ($(ARTOSYN_SDK_ROOT),)
OPENHD_CONF_OPTS += -DARTOSYN_SDK_LIB="$(OPENHD_ARTOSYN_CLIENT_LIB);$(OPENHD_ARTOSYN_COM_LIB)"
endif

define OPENHD_BUILD_ARTOSYN_SDK
	@if [ -z "$(ARTOSYN_SDK_ROOT)" ]; then \
		echo "ERROR: ARTOSYN_SDK_ROOT is not set for OpenHD"; \
		exit 1; \
	fi
	@if [ ! -d "$(ARTOSYN_SDK_ROOT)/host_drv/app/ar8030" ] || [ ! -d "$(ARTOSYN_SDK_ROOT)/host_drv/com" ]; then \
		echo "ERROR: Invalid ARTOSYN_SDK_ROOT=$(ARTOSYN_SDK_ROOT)"; \
		exit 1; \
	fi
	@if [ -n "$(ARTOSYN_SDK_LIB)" ]; then \
		echo "Using prebuilt Artosyn libs: $(ARTOSYN_SDK_LIB)"; \
	else \
		echo "Cross-building Artosyn SDK in Buildroot: $(OPENHD_ARTOSYN_BUILD_DIR)"; \
		rm -rf "$(OPENHD_ARTOSYN_BUILD_DIR)"; \
		mkdir -p "$(OPENHD_ARTOSYN_BUILD_DIR)"; \
		PATH="$(BR_PATH)" $(TARGET_MAKE_ENV) cmake \
			-S "$(ARTOSYN_SDK_ROOT)/host_drv" \
			-B "$(OPENHD_ARTOSYN_BUILD_DIR)" \
			-DCMAKE_TOOLCHAIN_FILE="$(HOST_DIR)/share/buildroot/toolchainfile.cmake" \
			-DAPP_STATIC_LIB=ON \
			-DBUILD_TEST_APP=OFF \
			-DBUILD_ARTOSYN_EXAMPLE=OFF \
			-DBUILD_RAM_INIT=OFF \
			-DBUILD_TUNTAP=OFF \
			-DBUILD_BW_UPDATE_DEMO=OFF \
			-DBUILD_IMG_UPGRADE=OFF \
			-DBUILD_XDATA_TEST=OFF \
			-DBUILD_REPEATER_TEST=OFF \
			-DBUILD_BB_TEST=OFF \
			-DBUILD_WORK_MODE_CFG=OFF \
			-DBUILD_NET_DEV_DEMO=OFF \
			-DENABLE_PYTHON=OFF \
			-DENABLE_JAVA=OFF \
			-DUSING_8030USB=ON \
			-DUSING_8030SDIO=OFF \
			-DUSING_8030UART=OFF \
			-DUSING_8030DRV=OFF; \
		PATH="$(BR_PATH)" $(TARGET_MAKE_ENV) cmake \
			--build "$(OPENHD_ARTOSYN_BUILD_DIR)" \
			--target ar8030_client com; \
		test -f "$(OPENHD_ARTOSYN_CLIENT_LIB)"; \
		test -f "$(OPENHD_ARTOSYN_COM_LIB)"; \
	fi
endef

OPENHD_PRE_CONFIGURE_HOOKS += OPENHD_BUILD_ARTOSYN_SDK

define OPENHD_INSTALL_TARGET_CMDS
	$(info OpenHD Build Directory: $(@D))
	$(INSTALL) -D -m 0755 $(@D)/$(OPENHD_SUBDIR)/openhd $(TARGET_DIR)/usr/bin/openhd
	$(INSTALL) -d $(TARGET_DIR)/etc/init.d
	cp -r $(@D)/../../../package/OpenHD/start.sh $(TARGET_DIR)/etc/init.d/S99openhd
	chmod +x $(TARGET_DIR)/etc/init.d/S99openhd
endef

$(eval $(cmake-package))
