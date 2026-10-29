include $(TOPDIR)/rules.mk

PKG_NAME:=x28-bootok
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-bootok
  SECTION:=base
  CATEGORY:=Base system
  TITLE:=Reset the slot-A boot tries after a good boot
  DEPENDS:=+dropbear
  PKGARCH:=all
endef

define Package/x28-bootok/description
  Init script that, once SSH and the LAN are up, writes 0 to slot A's tries byte in the four misc copies with the
  vendor dd-nand helper (supplied separately with libnandapi.so), as stock does after a good boot. Nothing else is written.
endef

define Build/Compile
endef

define Package/x28-bootok/install
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/x28-bootok.init $(1)/etc/init.d/x28-bootok
endef

$(eval $(call BuildPackage,x28-bootok))
