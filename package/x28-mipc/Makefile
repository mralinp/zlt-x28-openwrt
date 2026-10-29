include $(TOPDIR)/rules.mk

PKG_NAME:=x28-mipc
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-mipc
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=WWAN
  TITLE:=Native X28 MIPC netifd protocol (IPv4, IPv6, APN from SIM)
  DEPENDS:=+netifd +jshn +flock +mipc-wan
  PKGARCH:=all
endef

define Package/x28-mipc/description
  Native UCI/netifd protocol for a pre-initialized X28 modem: IPv4, IPv6 or IPv4v6, and an APN that
  is automatic from the SIM (AOSP-format /etc/conf/apns-conf_8.xml), picked from the SIM's list, or typed.
  Requires the separately supplied, ABI-compatible MIPC hardware stack.
  This package does not configure, stop or replace vendor services.
endef

define Build/Compile
endef

define Package/x28-mipc/install
	$(INSTALL_DIR) $(1)/lib/netifd/proto
	$(INSTALL_BIN) ./files/x28_mipc.sh $(1)/lib/netifd/proto/x28_mipc.sh
	$(INSTALL_DIR) $(1)/sbin
	$(INSTALL_BIN) ./files/x28-apn $(1)/sbin/x28-apn
endef

$(eval $(call BuildPackage,x28-mipc))
