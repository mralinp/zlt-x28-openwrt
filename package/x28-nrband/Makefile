include $(TOPDIR)/rules.mk

PKG_NAME:=x28-nrband
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-nrband
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=WWAN
  TITLE:=5G (NR) band mask of the X28 modem
  DEPENDS:=+mipc-wan
endef

define Package/x28-nrband/description
  Reads and sets the NR band mask over MIPC with the generic calls libmipc_msg.so exports (no vendor
  headers). Used by x28_mipc for the 5G band lock. Not built by the OpenWrt buildroot yet: tools/build/x28_nrband.sh
  builds it for the device.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) ./src/* $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) -o $(PKG_BUILD_DIR)/x28-nrband $(PKG_BUILD_DIR)/x28-nrband.c $(TARGET_LDFLAGS) -lmipc_msg
endef

define Package/x28-nrband/install
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/x28-nrband $(1)/usr/sbin/x28-nrband
endef

$(eval $(call BuildPackage,x28-nrband))
