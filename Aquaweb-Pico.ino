// Aquaweb-Pico
// Use a RP2040 Pico, a W5500 ethernet module, and a 3.3V-compliant SP485 to emulate a Jandy Square Remote
// (c) 2026, Earle F. Philhower, III <earlephilhower@yahoo.com>
// Released under GPL3 license
// Part of https://github.com/earlephilhower/aquaweb

#include <WiFi.h>
#include <WiFiClient.h>
#include <WebServer.h>
#include <SimpleMDNS.h>
#include <HTTPUpdateServer.h>
#include <W5500lwIP.h>
#include <WebSocketsServer.h>

// Ensure OTA is possible, requires a FS
static_assert(FS_END - FS_START > 1024 * 1023, "Need to define a filesystem of 1MB or greater");

// Wired exactly as in the WizNet W5500-EVB-Pico
Wiznet5500lwIP eth(17, SPI, 21);

WebServer httpServer(80);
HTTPUpdateServer httpUpdater;
WebSocketsServer webSocket(81);

// Raw data stream, ping pong buffer to avoid long locking
WebSocketsServer rawSocket(82);
constexpr size_t RAWMAX = 1024;
std::vector<uint8_t> rawData[2];
mutex_t rawMutex;
bool rawReady = false;
std::vector<uint8_t> *rawWriter;
std::vector<uint8_t> *rawReader;
uint8_t rawBuffer[RAWMAX + 1];

// MDNS hostname
const char* hostname = "aquaweb-pico";


// 3.3V RS485 interface, RTS manually controlled
const int rx = 1;
const int tx = 0;
const int rts = 3;


// For the RS485 protocol
const uint8_t NUL = 0x00;
const uint8_t DLE = 0x10;
const uint8_t STX = 0x02;
const uint8_t ETX = 0x03;

// Last read byte time (to ensure turnaround time)
uint32_t lastRead = 0;

const uint8_t favicon[] = {
  0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x10, 0x10, 0x02, 0x00, 0x01, 0x00,
  0x01, 0x00, 0xb0, 0x00, 0x00, 0x00, 0x16, 0x00, 0x00, 0x00, 0x28, 0x00,
  0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x01, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0xff,
  0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xfe, 0xbf, 0x00, 0x00, 0xd0, 0x07,
  0x00, 0x00, 0x8a, 0x89, 0x00, 0x00, 0x1f, 0x70, 0x00, 0x00, 0x3e, 0xbc,
  0x00, 0x00, 0x11, 0xd4, 0x00, 0x00, 0x9f, 0xa1, 0x00, 0x00, 0xd1, 0x57,
  0x00, 0x00, 0xfa, 0xa6, 0x00, 0x00, 0xf7, 0xd1, 0x00, 0x00, 0xff, 0xcb,
  0x00, 0x00, 0xff, 0xdf, 0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff,
  0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xfe, 0xbf,
  0x00, 0x00, 0xd0, 0x07, 0x00, 0x00, 0x8a, 0x89, 0x00, 0x00, 0x1f, 0x70,
  0x00, 0x00, 0x3e, 0xbc, 0x00, 0x00, 0x11, 0xd4, 0x00, 0x00, 0x9f, 0xa1,
  0x00, 0x00, 0xd1, 0x57, 0x00, 0x00, 0xfa, 0xa6, 0x00, 0x00, 0xf7, 0xd1,
  0x00, 0x00, 0xff, 0xcb, 0x00, 0x00, 0xff, 0xdf, 0x00, 0x00, 0xff, 0xff,
  0x00, 0x00, 0xff, 0xff, 0x00, 0x00
};




char logs[10000] = {};
void log(const char *str) {
  if (strlen(logs) > 8000) {
    logs[0] = 0;
  }
  strcat(logs, str);
  strcat(logs, "\n");
}

void logHex(const uint8_t *data, int len, const char *prefix = "") {
  if (strlen(logs) > 8000) {
    logs[0] = 0;
  }
  char buff[len * 2 + 4];
  char cx[3];
  buff[0] = 0;
  for (int i = 0; i < len; i++) {
    sprintf(cx, "%02x", data[i]);
    strcat(buff, cx);
  }
  strcat(logs, prefix);
  strcat(logs, buff);
  strcat(logs, "\n");
}


// All UART handling on the 2nd core since it is a little time critical.  We paid for the core, why not use it?




class Message {
  public:
    uint8_t dest;
    uint8_t cmd;
    std::vector<uint8_t> args;
    uint32_t lastTime;
    static constexpr size_t MAXARGS = 255;
    static constexpr uint32_t TIMEOUT = 1000; // 1 Second

    Message() {
      args.reserve(MAXARGS + 1); // Larger than largest message
      clear();
    }

    bool timeout() {
      return (millis() - lastTime) > TIMEOUT;
    }

    void clear() {
      dest = 0;
      cmd = 0;
      args.clear();
      lastTime = millis();
    }

    bool add(uint8_t c) {
      if (args.size() >= MAXARGS) {
        clear();
        return false;
      }

      args.push_back(c);
      lastTime = millis();
      return true;
    }

    uint8_t checksum() {
      uint8_t c = 0;
      c += 0x10; // DLE
      c += 0x02; // STX
      c += dest;
      c += cmd;
      for (auto x : args) {
        c += x;
      }
      return c;
    }

    void send() {
      static std::vector<uint8_t> out;
      out.clear();
      out.push_back(DLE);
      out.push_back(STX);
      out.push_back(dest);
      out.push_back(cmd);
      out.insert(out.end(), args.begin(), args.end());
      out.push_back(checksum());
      out.push_back(DLE);
      out.push_back(ETX);
      digitalWrite(rts, HIGH);
      Serial1.write(out.data(), out.size());
      Serial1.flush();
      digitalWrite(rts, LOW);
    }
};



Message msg;

class Screen {
  public:
    size_t W = 16;
    size_t H = 12;
    uint8_t ID = 0x40;
    uint8_t ACK = 0x8b;

    Screen() : dirty_(true), nextAck_(0x00) {
      invert_.line = -1;
      invert_.start = -1;
      invert_.end = -1;
      mutex_init(&_mutex);
      begin();
    }

    virtual ~Screen() {
      end();
    }

    void end() {
      while (screen_.size()) {
        free(screen_.back());
        screen_.pop_back();
        free(scratch_.back());
        scratch_.pop_back();
      }
    }

    void begin() {
      for (size_t i = 0; i < H; i++) {
        uint8_t *line = (uint8_t *)malloc(W);
        memset(line, ' ', W);
        screen_.push_back(line);
        line = (uint8_t *)malloc(W);
        memset(line, ' ', W);
        scratch_.push_back(line);
      }
    }

    void cls() {
      CoreMutex m(&_mutex);
      for (size_t i = 0; i < H; ++i) {
        memset(screen_[i], ' ', W);
      }
      invert_.line = -1;
      dirty_ = true;
    }

    void scroll(size_t start, size_t end, int direction) {
      CoreMutex m(&_mutex);
      if (direction == 255) { // -1
        for (size_t x = start; x < end; ++x) {
          memcpy(screen_[x], screen_[x + 1], W);
        }
        memset(screen_[end], ' ', W);
      } else if (direction == 1) { // +1
        for (size_t x = end; x > start; --x) {
          memcpy(screen_[x], screen_[x - 1], W);
        }
        memset(screen_[start], ' ', W);
      }
      dirty_ = true;
    }

    void writeLine(size_t line, const uint8_t *args, size_t len) {
      CoreMutex m(&_mutex);
      memset(screen_[line], ' ', W);
      if (len > W) {
        len = W;
      }
      memcpy(screen_[line], args, len);
      dirty_ = true;
    }

    void invertLine(size_t line) {
      CoreMutex m(&_mutex);
      invert_.line = line;
      invert_.start = 0;
      invert_.end = W;
      dirty_ = true;
    }

    void invertChars(size_t line, size_t start, size_t end) {
      CoreMutex m(&_mutex);
      invert_.line = line;
      invert_.start = start;
      invert_.end = end;
      dirty_ = true;
    }

    bool dirty() {
      return dirty_;
    }

    String html(bool clear = false) {
      InvertState inv;
      // Work from a copy of screen so we don't lock out UART core too long
      do {
        CoreMutex m(&_mutex);
        noInterrupts();
        for (size_t i = 0; i < H; i++) {
          memcpy(scratch_[i], screen_[i], W);
        }
        inv = invert_;
        interrupts();
      } while (0);
      String ret = "<pre>";
      for (size_t x = 0; x < H; ++x) {
        if (x == inv.line) {
          for (size_t y = 0; y < W; ++y) {
            if (y == inv.start) {
              ret += "<span style=\"background-color: #FFFF00\"><b>";
            }
            ret += (char) scratch_[x][y];
            if (y == inv.end) {
              ret += "</b></span>";
            }
          }
          if (inv.end >= W) {
            ret += "</b></span>";
          }
          ret += "\n";
        } else {
          String line((const char *)scratch_[x], W);
          ret += line + "\n";
        }
      }
      ret += "</pre>";
      if (clear) {
        dirty_ = false;
      }
      return ret;
    }

    void sendAck() {
      uint8_t thisAck;
      do {
        CoreMutex m(&_mutex);
        thisAck = nextAck_;
        nextAck_ = 0;
      } while (0);

      Message m;
      m.dest = 0x00;
      m.cmd = 0x01;
      m.add(ACK);
      m.add(thisAck);
      m.send();
    }

    void setNextAck(uint8_t nextAck) {
      nextAck_ = nextAck;
    }

    void sendKey(const String &key) {
      if (key == "up") {
        setNextAck(0x06);
      } else if (key == "down") {
        setNextAck(0x05);
      } else if (key == "back") {
        setNextAck(0x02);
      } else if (key == "select") {
        setNextAck(0x04);
      } else if (key == "pgup") {
        setNextAck(0x01);
      } else if (key == "pgdn") {
        setNextAck(0x03);
      }
    }

    void processMessage() {
      // Ensure we have some delay for turnaround time on the RS485 bus
      while (millis() - lastRead < 10) {
        delayMicroseconds(10);
      }

      sendAck();

      if (msg.cmd == 0x09) { // Clear Screen
        cls();
      } else if (msg.cmd == 0x0f) { // Scroll Screen
        if (msg.args.size() >= 3) {
          int start = msg.args[0];
          int end = msg.args[1];
          int direction = msg.args[2];
          scroll(start, end, direction);
        }
      } else if (msg.cmd == 0x04) { // Write a line
        if (!msg.args.empty()) {
          int line = msg.args[0];
          size_t offset = 1;
          uint8_t text[W];
          memset(text, ' ', W);
          while ((offset < msg.args.size()) && (msg.args[offset] != 0) && (offset < W + 1)) {
            text[offset - 1] = msg.args[offset]; // += static_cast<char>(msg.args[offset]);
            ++offset;
          }

          if (line == 64) {
            line = 0;  // Time (0x40)
          }
          if (line == 130) {
            line = 2;  // Temp (0x82)
          }

          writeLine(line, text, W);
        }
      } else if (msg.cmd == 0x05) {
        // Initial handshake? no-op
      } else if (msg.cmd == 0x00) {
        // PROBE no-op
      } else if (msg.cmd == 0x02) {
        //setStatus(toHex(ret.args));
      } else if (msg.cmd == 0x08) {
        if (!msg.args.empty()) {
          invertLine(msg.args[0]);
        }
      } else if (msg.cmd == 0x10) {
        if (msg.args.size() > 3) {
          invertChars(msg.args[0], msg.args[1], msg.args[2]);
        }
      } else {
        // Unknown
      }
    }

  protected:
    struct InvertState {
      size_t line;
      size_t start;
      size_t end;
    };

    bool dirty_;
    InvertState invert_;
    uint8_t nextAck_;
    mutex_t _mutex;
    std::vector<uint8_t *> screen_;
    // A copy only updated when HTML called, so we don't lock out the 2nd core too long while making complicated HTML String
    std::vector<uint8_t *> scratch_;
};





Screen screen;




void handleKey() {
  if (httpServer.hasArg("key")) {
    screen.sendKey(httpServer.arg("key"));
    httpServer.send(200, "text/html", String("<html><head><title>key</title></head><body>") + httpServer.arg("key") + String("</body></html>\n"));
  } else {
    httpServer.send(200, "text/html", "<html><head><title>key</title></head><body>error</body></html>");
  }
}

void handleScreen() {
  httpServer.send(200, "text/html", screen.html());
}



void processPacket() {
  uint8_t checksum = msg.args.back();
  msg.args.pop_back();
  if (checksum != msg.checksum()) {
    // Error, checksum failed
    return;
  }

  if (msg.dest == screen.ID) {
    screen.processMessage();
  }

}



void setup1() {
  mutex_init(&rawMutex);
  do {
    CoreMutex m(&rawMutex); // Lock it
    rawData[0].reserve(RAWMAX + 1);
    rawData[1].reserve(RAWMAX + 1);
    rawWriter = &rawData[0];
    rawReader = &rawData[1];
  } while (0);
  Serial1.setRX(rx);
  Serial1.setTX(tx);
  pinMode(rts, OUTPUT);
  digitalWrite(rts, LOW);
  Serial1.begin(9600);
}


// State machine
typedef enum {
  WAITSTART = 0, WAITSTX, DEST, CMD, SKIP0, ARGS, WAITETX
} State;
State state = WAITSTART;


void loop1() {
  if (!Serial1.available()) {
    if (msg.timeout()) {
      msg.clear();
      state = WAITSTART;
      log("timeout");
    }
  } else {
    uint8_t x = Serial1.read(); // Guaranteed available
    lastRead = millis();
    do {
      CoreMutex m(&rawMutex);
      if (rawWriter->size() == RAWMAX) {
        auto a = rawWriter;
        rawWriter = rawReader;
        rawReader = a;
        rawWriter->clear();
      }
      rawWriter->push_back(x);
      rawReady = true;
    } while (0);
    switch (state) {
      case WAITSTART:
        if (x == DLE) {
          state = WAITSTX;
        }
        break;

      case WAITSTX:
        if (x == STX) {
          state = DEST;
        } else if (x == DLE) {
          // Error, but we sat DLE so stay here
        } else {
          // error
          state = WAITSTART;
          msg.clear();
        }
        break;

      case DEST:
        msg.dest = x;
        state = CMD;
        break;

      case CMD:
        msg.cmd = x;
        if (msg.cmd == DLE) {
          // When DLE is in the message or data, the central will add a 0 after it
          state = SKIP0;
        } else {
          state = ARGS;
        }
        break;

      case SKIP0:
        state = ARGS;
        break;

      case ARGS:
        if (x == DLE) {
          state = WAITETX;
        } else if (!msg.add(x)) {
          // Weird overflow, toss
          state = WAITSTART;
          msg.clear();
        }
        break;

      case WAITETX:
        if (x == 0) {
          msg.add(DLE);
          state = ARGS; // This was an escaped 0x10, not a DLE
        } else if (x == ETX) {
          // Success
          processPacket();
          state = WAITSTART;
          msg.clear();
        } else if (x == DLE) {
          state = WAITSTX; // Weird error but could be start
          msg.clear();
        } else {
          msg.clear();
          state = WAITSTART;
        }
        break;
    }
  }
}


void connectOrReboot() {
  eth.end();

  // Start the Ethernet port
  if (!eth.begin()) {
    Serial.println("No wired Ethernet hardware detected. Check pinouts, wiring.");
    delay(5000);
    rp2040.reboot();
  }

  uint32_t start = millis();
  while (!eth.connected() && (start - millis() < 10000)) {
    Serial.print(".");
    delay(100);
  }
  if (!eth.connected()) {
    Serial.println("Unable to get an IP address, rebooting");
    delay(5000);
    rp2040.reboot();
  }
}


void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  char key[32];
  size_t len;
  IPAddress ip;
  String s;
  
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.printf("[%u] Disconnected!\n", num);
      break;
    case WStype_CONNECTED:
      ip = webSocket.remoteIP(num);
      Serial.printf("[%u] Connected from %d.%d.%d.%d url: %s\n", num, ip[0], ip[1], ip[2], ip[3], payload);
      // Send initial screen, but don't mark it clean
      s = screen.html(false);
      webSocket.sendTXT(num, s);
      break;
    case WStype_TEXT:
      len = std::min(length, sizeof(key) - 1);
      memcpy(key, payload, len);
      key[len] = 0;
      screen.sendKey(key);
      break;
    default:
      /*noop*/
      break;
  }
}

const char *SCREENWS = R"EOF(
<!doctype html>
<html>
<head>
<title>Pool Controller</title>
<script language="Javascript">
var connection = new WebSocket('ws://'+location.hostname+':81/', ['arduino']);
connection.onopen = function () { connection.send('Connect ' + new Date()); };
connection.onerror = function (error) { console.log('WebSocket Error ', error);};
connection.onmessage = function (e) { document.getElementById("screen").innerHTML = e.data; };
connection.onclose = function () { document.getElementById("screen").innerHTML = "<pre>DISCONNECTED</pre>"; };
function sendkey(k) { connection.send(k); };
</script>
</head>
<body>

<table>
<tr>
<td>
<table><tr><td height="80px" align="right"><button onclick="sendkey('pgup');">Page Up</button></td></tr><tr><td align="right" height="80px"><button onclick="sendkey('back');">Back</button></td></tr><tr><td align="right" height="80px"><button onclick="sendkey('pgdn');">Page Down</button></td></tr></table>
</td>
<td>
<font size="+2"><div id="screen"></div> </font>
</td>
<td>
    <table><tr><td align="left" height="80px"><button onclick="sendkey('up');">Up</button></td></tr><tr><td align="left" height="80px"><button onclick="sendkey('down');">Down</button></td></tr></table>
</td>
</tr>
<tr><td colspan="3" align="center"><button onclick="sendkey('select');">Select</button></td></tr>
</table>
</body>
</html>
)EOF";


void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println();
  Serial.println("Starting Ethernet port");

  connectOrReboot();

  Serial.println("");
  Serial.println("Ethernet connected");
  Serial.println("IP address: ");
  Serial.println(eth.localIP());

  MDNS.begin(hostname);
  MDNS.addService("http", "tcp", 80);
  MDNS.addService("ws", "tcp", 81);

  httpUpdater.setup(&httpServer);
  httpServer.on("/favicon.ico", []() { httpServer.send(200, "image/x-icon", (const char *)favicon, sizeof(favicon)); });
  httpServer.on("/log", []() { httpServer.send(200, "text/plain", logs); logs[0] = 0; });
  httpServer.on("/reboot", []() { httpServer.send(200, "text/plain", "Rebooting"); delay(1000); rp2040.reboot(); });
  httpServer.on("/status", []() { char buff[100]; sprintf(buff, "Uptime(ms): %llu\nFree Heap (bytes): %d\nTemp (C): %0.2f", rp2040.getCycleCount64() / F_CPU, rp2040.getFreeHeap(), analogReadTemp()); httpServer.send(200, "text/plain", buff); });
  httpServer.on("/", []() { httpServer.send(200, "text/html", SCREENWS); });
  httpServer.begin();

  webSocket.begin();
  webSocket.onEvent(webSocketEvent);

  rawSocket.begin();

  NTP.begin("pool.ntp.org", "time.nist.gov");
}

void loop() {
  if (eth.connected()) {
    httpServer.handleClient();
    MDNS.update();
    webSocket.loop();
    rawSocket.loop();

    if (screen.dirty()) {
      String s = screen.html(true);
      webSocket.broadcastTXT(s);
    }

    if (rawReady) {
      size_t sz;
      do {
        CoreMutex m(&rawMutex);
        noInterrupts();
        memcpy(rawBuffer, rawReader->data(), rawReader->size());
        rawReady = false;
        sz = rawReader->size();
        rawReader->clear();
        interrupts();
      } while (0);

      if (sz) {
        rawSocket.broadcastBIN(rawBuffer, sz);
      }
    }
  } else {
    connectOrReboot();
  }
}
