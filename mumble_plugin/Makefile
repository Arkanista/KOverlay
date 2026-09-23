CXX ?= g++
CXXFLAGS ?= -O2 -Wall -Wextra -fPIC -std=c++17 -Iinclude
LDFLAGS ?= -shared -lpthread

TARGET = koverlay_mumble.so
SOURCES = koverlay_mumble.cpp
PLUGINS_DIR = $(HOME)/.local/share/Mumble/Mumble/Plugins

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

install: $(TARGET)
	mkdir -p "$(PLUGINS_DIR)"
	cp $(TARGET) "$(PLUGINS_DIR)/"
	@echo "Plugin installed to $(PLUGINS_DIR)/$(TARGET)"

clean:
	rm -f $(TARGET)

.PHONY: all install clean
