include $(TOPDIR)/rules.mk

PKG_NAME:=x28-sysupgrade
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-sysupgrade
  SECTION:=base
  CATEGORY:=Base system
  TITLE:=Sysupgrade hooks for the X28 A/B layout (not shipped yet)
  PKGARCH:=all
endef

define Build/Compile
endef

define Package/x28-sysupgrade/install
	$(INSTALL_DIR) $(1)/lib/upgrade
	$(INSTALL_DATA) ./files/lib/upgrade/x28.sh $(1)/lib/upgrade/x28.sh
endef

$(eval $(call BuildPackage,x28-sysupgrade))
