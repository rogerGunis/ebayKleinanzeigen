# ebayKleinanzeigen

## Features

* **New** Upload all images from a set subdirectory

* **New** Configure shipping type in ad config

* Automatically deletes and re-publishes ad if existing one is too old

* Keeps track of ad publishing and last updating date

* Ability to selectively enable / disable ads being published / updated

* Overrides auto detected category (if `caturl` is specified) and fills the form data

* Uploads multiple photos

## Project structure

* `ebayKleinanzeigen`
  * `src`: python code
  * `data`: place for custom `config.json`, `.log` files are saved here

## Installation

There are two possible ways to run the project:

   1. Install all the requirements locally: python version and relevant libraries, firefox, geckodriver for selenium
   2. Work with a self-contained dockerized version of the project
The sections below describe installation steps for both approaches

### Installation Guide: Dockerized project

#### *Writing code INSIDE container*

* Install [Docker](https://docs.docker.com/get-docker/)

The easiest way to work with the project is by using *VS Code* and its *Remote Containers extension*. This approach, unlike the following one, allows us to use the docker container both for development and running the application. All the project dependencies (python version and libraries, firefox and geckodriver installation) as well as VS Code set-up are taken care of by the container set-up. 

* Install [VS Code](https://code.visualstudio.com/download)
* Install [VS Code Remote Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension
* Checkout the project with `git clone`
* Enable access to your host X server
  * Ubuntu: execute `xhosts +` on the host
  * Windows / Mac OS: not tested, refer to this [source](https://medium.com/better-programming/running-desktop-apps-in-docker-43a70a5265c4)
    * further configurations in `devcontainer.json` will likely be needed
* Open the project in container and start development
  * ![Opening project in VS Code remote container](https://microsoft.github.io/vscode-remote-release/images/remote-containers-readme.gif)
  * `launch.json` already defines one debug configuration that can be used right away
  * Docker image has Firefox and geckdriver installed, they will be spun off from the container and shown on the host

#### *Writing code on the host but running it inside Docker*

 Alternatively (not a well tested option), one can start a docker container with its volumes linked to the project directory on the host. This way, all the code editing happens on the host and the changes are mirrored back in the container. After editing is done:

* `cd` to project folder
* Build image from the `Dockerfile`
  * `docker build -t ebaykleinanzeigen:1.0 .`
* Start up container in interactive mode
  * `docker run -it --workdir="/app" -e DISPLAY=$DISPLAY --mount=source=/tmp/.X11-unix,target=/tmp/.X11-unix,type=bind -v $(pwd):/app --name ebaykleinanzeigen ebaykleinanzeigen:1.0`
* inside the container:
  * `cd src`
  * `python3 kleinanzeigen.py --profile=../data/config.json` (`config.json`) should be there
* Debugging while inside docker: IDK...

### Installation Guide: Prerequisites for **not Dockerized** development environments

* config.json (from config.json.example)
* geckodriver (to /usr/local/bin): <https://github.com/mozilla/geckodriver/releases>
* selenium: ```pip install selenium```

### Installation Guide: Ubuntu

1. Install Python 3 and PIP

    `sudo apt-get install python3 python3-pip`

2. Install Selenium

    `pip3 install selenium`

3. Install Gecko Driver and move it to /usr/bin

   * Check the [release Page](https://github.com/mozilla/geckodriver/releases) of Mozilla and replace #RELEASE# with the current release number, e.g. v0.26.0

      `wget https://github.com/mozilla/geckodriver/releases/download/#RELEASE#/geckodriver-#RELEASE#-linux64.tar.gz`

   * Extract the file

      `tar xzf geckodriver-#RELEASE#-linux64.tar.gz`

   * Move the driver to it's preferred location

      `sudo mv geckodriver /usr/bin/geckodriver`

4. clone the app from git

    `git clone https://github.com/donwayo/ebayKleinanzeigen`

5. configure the app

   * go to the Project-Folder

   * copy the sample to a new file

      `cp config.json.example config.json`

   * edit the file and fill in your details.

   * to find out the categories you need to start posting an ad on the website and then copy the corresponding link to the category from there. It's the screen where you select the category.

6. Start the app

   * go to the app folder

      `python3 kleinanzeigen.py --profile config.json`

   * if launching from VS Code, the following path variable should be set when not in headless mode:

      `export DISPLAY=":0"` ([source](https://stackoverflow.com/a/61672397/256002))

Now a browser window should start, login and fill out the fields automatically.

### Installation Guide: MacOS, Tested on catalina

```bash
# create new virtual env, for instance with conda
conda create --name ebayKleinanzeigen python=3.7
conda activate ebayKleinanzeigen
pip install selenium
brew install geckodriver

# if firefox is not installed yet
brew cask install firefox

git clone https://github.com/donwayo/ebayKleinanzeigen

# open config and enter your preferences. For cat_url, see below
cp config.json.example config.json
```

* To run the app, run `python kleinanzeigen.py --profile config.json`

* to find out the categories you need to start posting an ad on the website and then copy the corresponding link to the category from there. It's the screen where you select the category.

Now a browser window should start, login and fill the fields automatically.

### Installation Guide: Windows

1. Download and install Python 3 for Windows from <https://www.python.org/downloads/>

2. create a `ebayKleinanzeigen` directory somewhere you want

3. move to Python script installation directory and install some requirements

    ```bat
    cd C:\Users\ulrik\AppData\Local\Programs\Python\Python39\Scripts

    pip install selenium
    ```

4. download and extract the Gecko Driver for windows from <https://github.com/mozilla/geckodriver/releases> and place it in the ebayKleinanzeigen directory

5. download the ebayKleinanzeigen app from git and extract it to the ebayKleinanzeigen directory

6. configure the app

   * go to the ebayKleinanzeigen directory

   * copy the sample to a new file

      `cp config.json.example config.json`

   * edit the file and fill in your details.

   * to find out the categories you need to start posting an ad on the website and then copy the corresponding link to the category from there. It's the screen where you select the category.

7. Start the app

   * go to the ebayKleinanzeigen directory

      `python3 kleinanzeigen.py --profile config.json`

Now a browser window should start, login and fill the fields automatically.

## Additional Category fields

|   |   | |
|---|---| ---|
| Elektronik > Foto  | `foto.art_s`         | `Kamera`, `Objektiv`, `Zubehör`, `Kamera & Zubehör` |
| Elektronik > Foto  | `foto.condition_s`   | `Neu`, `Gebraucht`, `Defekt`          |

## Credits

* @Lopp0 - initial script

* @donwayo - Fixes and improvements

* @MichaelKueller - Python 3 migration and cleanup

* @n3amil - Fixes and improvements

* @x86dev - Fixes and improvements

* @neon-dev - Fixes and improvements

* @kahironimashte - Install guide

* @therealsupermario - Description Files, ad-level zip codes, custom update interval, support for additional category fields

* @denisergashbaev - Dockerization for VS Code with remote containers extension