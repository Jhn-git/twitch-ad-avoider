Installation
============

Requirements
------------

* Python 3.8 or higher
* streamlink 5.0.0 or higher

Dependencies
------------

Core dependencies:

* **streamlink**: Stream extraction and playback
* **typing-extensions**: Enhanced type hints for older Python versions

Development dependencies:

* **pytest**: Testing framework
* **black**: Code formatting
* **flake8**: Code linting
* **mypy**: Type checking
* **sphinx**: Documentation generation

Installation Steps
------------------

1. **Clone the repository**::

    git clone https://github.com/yourusername/twitch-viewer.git
    cd twitch-viewer

2. **Create virtual environment**::

    python -m venv venv
    
    # Windows
    venv\Scripts\activate
    
    # macOS/Linux
    source venv/bin/activate

3. **Install the application**::

    # Production installation
    pip install -e .
    
    # Development installation with all dependencies
    pip install -e .[dev]

4. **Verify installation**::

    python main.py --help

Player Installation
-------------------

TwitchAdAvoider requires a compatible video player. Install one of the following:

**VLC Media Player** (Recommended)
    * Windows: Download from https://www.videolan.org/vlc/
    * macOS: ``brew install --cask vlc``
    * Linux: ``sudo apt install vlc`` or equivalent

**MPV**
    * Windows: Download from https://mpv.io/installation/
    * macOS: ``brew install mpv``
    * Linux: ``sudo apt install mpv`` or equivalent

**MPC-HC** (Windows only)
    * Download from https://mpc-hc.org/downloads/

The application will automatically detect installed players, or you can specify a custom path in the settings.