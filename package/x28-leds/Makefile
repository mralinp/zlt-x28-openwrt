include $(TOPDIR)/rules.mk

PKG_NAME:=x28-leds
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/x28-leds
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=X28 front LEDs (power, Wi-Fi, 4G, 5G, signal)
  DEPENDS:=+jsonfilter +mipc-wan
  PKGARCH:=all
endef

define Package/x28-leds/description
  Drives the X28 front LEDs through the vendor tz_gpio_leds driver: power on, Wi-Fi on while a
  wireless interface is up, 4G/5G from the registered access technology (blinking until wan is up),
  and the RGB signal LED from RSRP (green, orange, red; blue blinking while not registered).
endef

define Build/Compile
endef

define Package/x28-leds/install
	$(INSTALL_DIR) $(1)/sbin $(1)/etc/init.d
	$(INSTALL_BIN) ./files/x28-leds $(1)/sbin/x28-leds
	$(INSTALL_BIN) ./files/x28-leds.init $(1)/etc/init.d/x28-leds
endef

$(eval $(call BuildPackage,x28-leds))
