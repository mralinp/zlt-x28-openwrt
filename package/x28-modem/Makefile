include $(TOPDIR)/rules.mk

PKG_NAME:=x28-modem
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-modem
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=WWAN
  TITLE:=Start the X28 modem stack at boot
  DEPENDS:=+x28-mipc
  PKGARCH:=all
endef

define Package/x28-modem/description
  Boot script for the X28's separately supplied vendor modem stack: partition name links, vendor
  yaffs2 mounts, the vendor daemons in the order verified on hardware, the one-ACM USB gadget
  atcid needs, then radio on and wan up. mtk_netagent is not started.
endef

define Build/Compile
endef

define Package/x28-modem/install
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/x28-modem.init $(1)/etc/init.d/x28-modem
endef

$(eval $(call BuildPackage,x28-modem))
