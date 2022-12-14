# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

OUTPUT_DIR = .
OUTPUT_JS = $(OUTPUT_DIR)/js/goofy.js
OUTPUT_CSS = $(OUTPUT_DIR)/css/closure.css

BUILD_DEPS = ../../../build_deps
CLOSURE_LIB_DIR = /opt/closure-library

JS_SOURCES = \
    device_manager.js \
    diagnosis_tool.js \
    goofy.js \
    i18n.js \
    plugin.js \
    test_ui/manager.js \
    test_ui/tab_manager.js \
    test_ui/tile_manager.js \
    utils.js

JS_SOURCE_PATHS = $(addprefix ../js/,$(JS_SOURCES))

CSS_SOURCES = \
    goog/css/button.css \
    goog/css/checkbox.css \
    goog/css/common.css \
    goog/css/custombutton.css \
    goog/css/dialog.css \
    goog/css/menu.css \
    goog/css/menuitem.css \
    goog/css/menuseparator.css \
    goog/css/submenu.css \
    goog/css/tab.css \
    goog/css/tabbar.css \
    goog/css/tooltip.css \
    goog/css/tree.css

CSS_SOURCE_PATHS = $(addprefix $(CLOSURE_LIB_DIR)/closure/,$(CSS_SOURCES))

CLOSURE_BUILD = \
    python3 $(CLOSURE_LIB_DIR)/closure/bin/build/closurebuilder.py \
    --root $(CLOSURE_LIB_DIR) \
    --root ../js \
    -n cros.factory.Goofy \
    -n cros.factory.Plugin

.PHONY: all clean check_deps check_js

all: $(OUTPUT_JS) $(OUTPUT_CSS)

clean:
	rm -f $(OUTPUT_JS) $(OUTPUT_CSS)

check_deps:
	$(if $(wildcard $(CLOSURE_LIB_DIR)),,\
	  $(info *** $(CLOSURE_LIB_DIR) does not exist.) \
	  $(info *** Please install it. For example, run this in chroot:) \
	  $(info ***) \
	  $(info ***   sudo emerge closure-library) \
	  $(info ***) \
	  $(error Terminating))

check_js: | check_deps
	# For now, we just use the compiler to check the correctness of our code, and
	# we actually deploy the version that is the concatenation of all the
	# dependencies (--output_mode=script).
	closure-compiler \
	  --warning_level=VERBOSE \
	  --jscomp_warning=lintChecks \
	  --hide_warnings_for=/opt/closure-library \
	  --language_in ECMASCRIPT_NEXT \
	  --dependency_mode=STRICT \
	  --entry_point cros.factory.Goofy \
	  --entry_point cros.factory.Plugin \
	  --externs ../js/externs.js \
	  --checks-only \
	  '$(CLOSURE_LIB_DIR)/**.js' \
	  $(JS_SOURCE_PATHS)

$(OUTPUT_JS): $(JS_SOURCE_PATHS) | check_deps
	mkdir -p "$(shell dirname "$@")"
	# TODO(pihsun): Change this to closure-compiler --compilation_level=BUNDLE
	# when there's newer closure-compiler-bin, and merge with the command of
	# check_js.
	$(CLOSURE_BUILD) --output_mode=script --output_file=$@

$(OUTPUT_CSS): $(CSS_SOURCE_PATHS) Makefile | check_deps
	mkdir -p "$(shell dirname "$@")"
	echo "/* This file is generated by Makefile */" >$@
	# Replace all references to URLs with resources in this project.
	sed -re 's"//ssl\.gstatic\.com/(closure|editor)"/images"g' \
	  $(CSS_SOURCE_PATHS) >>$@
