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
  TITLE:=Native X28 MIPC netifd protocol (experimental IPv4)
  DEPENDS:=+netifd +jshn +flock +mipc-wan
  PKGARCH:=all
endef

define Package/x28-mipc/description
  Native UCI/netifd IPv4 routing protocol for a pre-initialized X28 modem.
  Requires the separately supplied, ABI-compatible MIPC hardware stack.
  This package does not configure, stop or replace vendor services.
endef

define Build/Compile
endef

define Package/x28-mipc/install
	$(INSTALL_DIR) $(1)/lib/netifd/proto
	$(INSTALL_BIN) ./files/x28_mipc.sh $(1)/lib/netifd/proto/x28_mipc.sh
endef

$(eval $(call BuildPackage,x28-mipc))
