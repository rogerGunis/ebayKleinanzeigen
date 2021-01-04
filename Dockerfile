FROM ubuntu:20.04

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive && apt-get install -y --no-install-recommends wget bash zip rsync python3.6 python3-dev python3-pip dash unzip \ 
    build-essential git vim firefox gnupg2

RUN python3 -m pip install --upgrade pip==20.3.1

# [Optional] If your pip requirements rarely change, uncomment this section to add them to the image.
COPY src/requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp/requirements.txt

## Geckodriver
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.28.0/geckodriver-v0.28.0-linux64.tar.gz \
    && tar xzf geckodriver-v0.28.0-linux64.tar.gz && rm geckodriver-v0.28.0-linux64.tar.gz \
    && mv geckodriver /usr/bin/geckodriver

# Set the Chrome repo.
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list

# Install Chrome.
RUN apt-get update && apt-get -y install google-chrome-stable

## Chromedriver
RUN wget https://chromedriver.storage.googleapis.com/$(wget -qO - https://chromedriver.storage.googleapis.com/LATEST_RELEASE_87)/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    chmod +x chromedriver && \
    mv chromedriver /usr/bin/ && \
    rm chromedriver_linux64.zip

# adding non-root user as described in 
# https://stelligent.com/2020/05/29/development-acceleration-through-vs-code-remote-containers-how-we-leverage-vs-code-remote-containers-for-rapid-development-of-cfn_nag/
ARG USERNAME=container-dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
  && useradd --uid $USER_UID --gid $USER_GID --shell /bin/bash -m $USERNAME \
  && apt-get install -yq sudo \
  && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
  && chmod 0440 /etc/sudoers.d/$USERNAME

RUN chown -R $USERNAME /usr/bin/geckodriver

USER $USERNAME
