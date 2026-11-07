include $(TOPDIR)/rules.mk

PKG_NAME:=x28-dhcp
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-dhcp
  SECTION:=base
  CATEGORY:=Base system
  TITLE:=Restart dnsmasq if it came up without a DHCP range
  DEPENDS:=+dnsmasq
  PKGARCH:=all
endef

define Package/x28-dhcp/description
  Init script that, for the first 20 minutes after boot, restarts dnsmasq (at most 3 times) when the LAN has its address but
  dnsmasq's running config has no DHCP range, which is what happens when it starts before netifd can report the address.
endef

define Build/Compile
endef

define Package/x28-dhcp/install
	$(INSTALL_DIR) $(1)/etc/init.d $(1)/usr/libexec
	$(INSTALL_BIN) ./files/x28-dhcp.init $(1)/etc/init.d/x28-dhcp
	$(INSTALL_BIN) ./files/x28-dhcp-guard $(1)/usr/libexec/x28-dhcp-guard
endef

$(eval $(call BuildPackage,x28-dhcp))
