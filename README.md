# 🌐 Visionary Navigator

**A modern, privacy-focused desktop browser built with PyQt6, featuring AI integration, advanced privacy tools, and a glassmorphism aesthetic.**

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-Latest-41CD52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

## ✨ Features

### 🤖 AI Integration
- **AI Sidebar** - Gemini-powered assistant for intelligent browsing assistance
- **Voice Commands** - Control the browser with natural language
- **Vision AR** - Augmented reality capabilities for visual search

### 🔐 Privacy & Security
- **Privacy Engine** - Advanced tracker blocking and ad filtering
- **Ghost Sandbox** - Isolated browsing mode for sensitive tasks
- **Proxy Manager** - Multi-protocol proxy support (HTTP, HTTPS, SOCKS5)
  - Per-profile proxy assignment
  - Concurrent proxy validation
  - Automatic proxy fetching from public sources
- **Guardian Security** - Advanced threat detection and blocking
- **Profile Isolation** - Separate browsing profiles with individual settings

### 🎵 Entertainment
- **Music Player** - YouTube-integrated music streaming with modern UI
- **Video Moderator** - Intelligent video content filtering
- **Play Controls** - Picture-in-Picture, volume control, playback settings

### 💰 Finance Dashboard
- Real-time financial data
- Portfolio tracking
- Market insights

### 🎨 User Experience
- **Glassmorphism Design** - Modern ultra-premium UI aesthetic
- **Dark Theme** - Eye-friendly dark mode with gradient backgrounds
- **Responsive Layout** - Adapts seamlessly to different screen sizes
- **Gesture Controls** - Intuitive gesture-based navigation
- **Custom New Tab Page** - Digital clock, weather widget, quick access cards

### 🔍 Visionary Meta-Search Engine
- **Multi-Source Search** - Aggregate results from multiple search engines
- **Anonymous Searching** - Privacy-focused search without tracking
- **Beautiful Results Page** - Glassmorphism-styled search results
- **Source Badges** - Visual indicators for result sources

### 🌐 Advanced Browsing
- **Tab Management** - Efficient multi-tab browsing
- **Search Engine Selection** - Easy switching between Google, DuckDuckGo, Bing, Visionary
- **Settings Manager** - Comprehensive browser configuration
- **Resource Manager** - Smart memory and CPU management

## 🚀 Quick Start

### Requirements
- **Python 3.9+**
- **macOS 10.14+** or **Windows 10+**
- **4GB RAM** (minimum)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/alieneseren/tarayici.git
cd tarayici
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the browser**
```bash
python main.py
```

### Optional: Build Executable

**macOS:**
```bash
pyinstaller build_macos.spec
```

**Windows:**
```bash
pyinstaller build_windows.spec
```

## 📁 Project Structure

```
tarayici/
├── main.py                      # Entry point
├── browser_core.py              # Main browser window & tab management
├── new_tab_page.py              # New tab page with UI components
├── visionary_search.py          # Meta-search engine
├── proxy_engine.py              # Proxy management system
├── privacy_engine.py            # Privacy & tracker blocking
├── ai_logic.py                  # AI sidebar & Gemini integration
├── gesture_controller.py        # Gesture recognition
├── ghost_sandbox.py             # Isolated browsing mode
├── guardian_security.py         # Security features
├── music_fullpage.py            # Music player UI
├── finance_engine.py            # Finance dashboard
├── voice_engine.py              # Voice command processing
├── video_moderator.py           # Video content filtering
├── settings_manager.py          # Settings persistence
├── resource_manager.py          # Resource monitoring
├── config.py                    # Configuration constants
├── js/                          # JavaScript utilities
│   ├── dom_interceptor.js       # DOM manipulation
│   ├── qwebchannel.js           # QWebChannel integration
│   └── youtube_downloader.js    # YouTube integration
├── templates/                   # HTML templates
│   └── search_results.html      # Search results page
├── styles/                      # QSS stylesheets
│   └── theme.qss                # Dark theme
├── assets/                      # Icons and resources
└── requirements.txt             # Python dependencies
```

## 🎯 Key Components

### Proxy Engine (`proxy_engine.py`)
- **ProxyManager** - Manages per-profile proxy settings
- **ProxyValidator** - Concurrent proxy testing with health checks
- **ProxyFetcher** - Automatic proxy source integration
- **ProxyToast** - Beautiful Turkish notifications

### Visionary Search (`visionary_search.py`)
- Modern dark glassmorphism UI
- Parallel search from multiple engines
- Animated result cards
- Source-based color coding

### AI Sidebar (`ai_logic.py`)
- Gemini API integration
- Context-aware suggestions
- Voice input support

### New Tab Page (`new_tab_page.py`)
- Digital clock with Turkish date
- Search engine selector (dropdown menu)
- Quick access cards
- Weather widget
- Gradient backgrounds

## 🔧 Configuration

Edit `config.py` to customize:
- AI model settings
- Privacy engine sensitivity
- Proxy sources
- UI preferences
- Search engine defaults

## 🌍 Localization

The browser supports **Turkish (Türkçe)** as the primary language with:
- Turkish notifications and UI text
- Turkish date formatting
- Turkish voice command support

## 📦 Dependencies

Key packages:
- **PyQt6** - GUI framework
- **PyQt6-WebEngine** - Web rendering
- **requests** - HTTP client
- **google-generativeai** - Gemini API
- **psutil** - System monitoring

See `requirements.txt` for complete list.

## 🎓 Usage Examples

### Starting the Browser
```bash
python main.py
```

### Using Visionary Search
1. Click the search bar on the new tab page
2. Select "✨ Visionary" from the dropdown
3. Enter your search query
4. View aggregated results with source indicators

### Enabling Ghost Sandbox
1. Right-click in the browser
2. Select "Open in Ghost Sandbox"
3. Browse anonymously in isolated mode

### Setting Up Proxy
1. Click menu → Settings → Proxy
2. Select proxy type (HTTP/HTTPS/SOCKS5)
3. Enter host and port
4. The system validates and applies automatically

## 🐛 Troubleshooting

### ModuleNotFoundError for PyQt6
```bash
pip install PyQt6 PyQt6-WebEngine
```

### Proxy Connection Fails
- Check internet connection
- Verify proxy host and port
- Try a different proxy source

### Music Player Issues
- Ensure YouTube is accessible
- Check WebEngine permissions
- Clear browser cache

## 🚦 Roadmap

- [ ] Firefox profile sync
- [ ] Built-in VPN alternative
- [ ] Advanced fingerprint spoofing
- [ ] Chrome extension support
- [ ] Bookmark synchronization
- [ ] History encryption
- [ ] Multi-language support expansion

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under **MIT License with Commons Clause** - see the LICENSE file for details.

**Key Terms:**
- ✅ Free for personal, educational, and non-commercial use
- ✅ You can modify, study, and learn from the code
- ❌ Commercial use, selling, or SaaS deployment requires explicit permission
- ❌ Cannot be used to build competing commercial products

For commercial licensing inquiries, contact the copyright holder via GitHub.

## 🙋 Support

- **Issues** - Report bugs on [GitHub Issues](https://github.com/alieneseren/tarayici/issues)
- **Discussions** - Join community discussions
- **Email** - Contact via GitHub profile

## 🌟 Acknowledgments

- **PyQt6** team for the excellent framework
- **Google Generative AI** for Gemini integration
- **Privacy advocates** who inspired this project
- **Open source community** for amazing libraries

---

**Made with ❤️ for privacy-conscious developers**

*Visionary Navigator - Your gateway to intelligent, private browsing.*
