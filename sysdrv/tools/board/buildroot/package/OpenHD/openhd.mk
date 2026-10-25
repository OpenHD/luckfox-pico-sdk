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
OPENHD_PICO_BASE_ID ?= $(shell sha256sum $(CONFIG_DIR)/.config | cut -d' ' -f1)

# Dependencies
OPENHD_DEPENDENCIES = poco libsodium gstreamer1 gst1-plugins-base libpcap libusb librtlsdr ncurses host-pkgconf host-python3

OPENHD_ARTOSYN_BUILD_DIR = $(ARTOSYN_SDK_ROOT)/host_drv/build-openhd-buildroot
OPENHD_ARTOSYN_CLIENT_LIB = $(OPENHD_ARTOSYN_BUILD_DIR)/app/ar8030/libar8030_client.a
OPENHD_ARTOSYN_COM_LIB = $(OPENHD_ARTOSYN_BUILD_DIR)/com/libcom.a

# CMake options
OPENHD_CONF_OPTS = \
    -DENABLE_USB_CAMERAS=OFF \
    -DENABLE_GSTREAMER=OFF \
    -DOPENHD_MPP_ONLY=ON \
    -DOPENHD_PICO_MPI=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DOPENHD_ENABLE_DEVOURER=ON \
    -DBUILD_TESTING=OFF \
    -DPython3_EXECUTABLE=$(HOST_DIR)/bin/python3 \
    -DPYTHON_EXECUTABLE=$(HOST_DIR)/bin/python3 \
    -DCMAKE_EXE_LINKER_FLAGS="-lstdc++fs"

OPENHD_PICO_MEDIA_DIR = $(abspath $(OPENHD_PKGDIR)/../../../../../../media)
OPENHD_PICO_AIQ_DIR = $(OPENHD_PICO_MEDIA_DIR)/isp/release_camera_engine_rkaiq_rv1106_arm-rockchip830-linux-uclibcgnueabihf
OPENHD_CONF_OPTS += \
    -DPICO_MPI_INCLUDE_DIR=$(OPENHD_PICO_MEDIA_DIR)/rockit/rockit/mpi/sdk/include \
    -DPICO_MPI_LIBRARY=$(OPENHD_PICO_MEDIA_DIR)/rockit/rockit/lib/lib32/librockit.so \
    -DPICO_RKAIQ_INCLUDE_DIR=$(OPENHD_PICO_AIQ_DIR)/include/rkaiq/uAPI2 \
    -DPICO_RKAIQ_LIBRARY=$(OPENHD_PICO_AIQ_DIR)/lib/librkaiq.so

# Match the canonical Luckfox component builder: only the application target
# is installed, and Devourer must be linked into it rather than shipped as a DSO.
OPENHD_MAKE_OPTS = openhd

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

# removed artosyn hook

define OPENHD_INSTALL_TARGET_CMDS
	$(info OpenHD Build Directory: $(@D))
	$(INSTALL) -D -m 0755 $(@D)/$(OPENHD_SUBDIR)/openhd $(TARGET_DIR)/usr/bin/openhd
	$(INSTALL) -d $(TARGET_DIR)/etc/init.d
	$(INSTALL) -D -m 0755 $(OPENHD_PKGDIR)/start.sh $(TARGET_DIR)/etc/init.d/S99openhd
	$(INSTALL) -D -m 0755 $(OPENHD_PKGDIR)/pico-update.py $(TARGET_DIR)/usr/sbin/openhd-pico-update
	$(INSTALL) -D -m 0755 $(OPENHD_PKGDIR)/slots.sh $(TARGET_DIR)/etc/init.d/S97openhd-slots
	mkdir -p $(TARGET_DIR)/etc
	printf '%s\n' '$(OPENHD_PICO_BASE_ID)' > $(TARGET_DIR)/etc/openhd-pico-base-id
endef

$(eval $(cmake-package))

