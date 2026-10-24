###################################################################
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
# https://github.com/OpenHD/OpenHD-SysUtils
#
# © OpenHD, All Rights Reserved.
################################################################################
$(info Building the OpenHD-SysUtils package...)

# The Git repository from which to clone the source code
OPENHD_SYSUTILS_UPSTREAM_SITE = https://github.com/OpenHD/OpenHD-SysUtils.git
ifeq ($(OPENHD_SYSUTILS_LOCAL_SITE),)
OPENHD_SYSUTILS_SITE = $(OPENHD_SYSUTILS_UPSTREAM_SITE)
OPENHD_SYSUTILS_SITE_METHOD = git
OPENHD_SYSUTILS_GIT_SUBMODULES = YES
OPENHD_SYSUTILS_VERSION = $(shell git ls-remote $(OPENHD_SYSUTILS_SITE) refs/heads/dev-release | cut -f1)
else
OPENHD_SYSUTILS_SITE = $(OPENHD_SYSUTILS_LOCAL_SITE)
OPENHD_SYSUTILS_SITE_METHOD = local
OPENHD_SYSUTILS_VERSION = local
endif

# Install to the target system
OPENHD_SYSUTILS_INSTALL_TARGET = YES

# Build the daemon only; the vendor image uses BusyBox init
OPENHD_SYSUTILS_DEPENDENCIES = libusb usb_modeswitch util-linux
OPENHD_SYSUTILS_CONF_OPTS = -DBUILD_TESTING=OFF -DOPENHD_DEVOURER_RTL8812EU=ON

# Install init.d services to target
define OPENHD_SYSUTILS_INSTALL_TARGET_CMDS
    $(info OpenHD-SysUtils Build Directory: $(OPENHD_SYSUTILS_BUILDDIR))
    $(INSTALL) -D -m 0755 $(OPENHD_SYSUTILS_BUILDDIR)/openhd_sys_utils $(TARGET_DIR)/usr/bin/openhd_sys_utils
    $(INSTALL) -d $(TARGET_DIR)/etc/init.d
    $(INSTALL) -D -m 0755 $(OPENHD_SYSUTILS_PKGDIR)/start.sh $(TARGET_DIR)/etc/init.d/S98openhd-sysutils
    $(INSTALL) -D -m 0644 $(@D)/misc/openhd-devourer-eu.conf $(TARGET_DIR)/lib/modprobe.d/openhd-devourer-eu.conf
    $(INSTALL) -D -m 0644 $(@D)/misc/70-openhd-devourer-eu.rules $(TARGET_DIR)/lib/udev/rules.d/70-openhd-devourer-eu.rules
    $(INSTALL) -D -m 0644 $(@D)/misc/wifi_cards.json $(TARGET_DIR)/usr/local/share/OpenHD/SysUtils/wifi_cards.json
endef

# Use Buildroot's CMake package infrastructure to handle the build
$(eval $(cmake-package))
