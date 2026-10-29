include $(TOPDIR)/rules.mk

PKG_NAME:=x28-wifi
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-wifi
  SECTION:=net
  CATEGORY:=Network
  TITLE:=netifd wireless handler for the X28 MT7915 (mt_wifi)
  DEPENDS:=+netifd
  PKGARCH:=all
endef

define Package/x28-wifi/description
  Drives the X28's MT7915 DBDC (ra0 2.4 GHz, rai0 5 GHz) on MediaTek's mt_wifi driver from
  /etc/config/wireless, so stock LuCI's Wireless page works and the APs join their network bridge.
  Requires the separately supplied mt_wifi module, /etc/wireless/l1profile.dat and the stock
  mt7915.dbdc.b0/b1.dat profiles; calibration stays in /mnt/vendor/nvcfg/e2p.
endef

define Build/Compile
endef

define Package/x28-wifi/install
	$(INSTALL_DIR) $(1)/lib/netifd/wireless $(1)/lib/wifi
	$(INSTALL_BIN) ./files/mtwifi.sh $(1)/lib/netifd/wireless/mtwifi.sh
	$(INSTALL_DATA) ./files/mtwifi.detect $(1)/lib/wifi/mtwifi.sh
endef

$(eval $(call BuildPackage,x28-wifi))
