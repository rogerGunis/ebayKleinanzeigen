FROM ubuntu:18.04

RUN apt-get update

RUN apt-get -y install wget bash zip rsync python3.6 python3-pip \ 
    build-essential git vim
RUN python3 -m pip install --upgrade pip==20.3.1

# [Optional] If your pip requirements rarely change, uncomment this section to add them to the image.
COPY src/requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp/requirements.txt

RUN apt -y install firefox
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.26.0/geckodriver-v0.26.0-linux64.tar.gz \
    && tar xzf geckodriver-v0.26.0-linux64.tar.gz && rm geckodriver-v0.26.0-linux64.tar.gz \
    && mv geckodriver /usr/bin/geckodriver

# adding non-root user as described in 
# https://stelligent.com/2020/05/29/development-acceleration-through-vs-code-remote-containers-how-we-leverage-vs-code-remote-containers-for-rapid-development-of-cfn_nag/
ARG USERNAME=container-dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
  && useradd --uid $USER_UID --gid $USER_GID --shell /bin/bash -m $USERNAME \
  && apt-get install -y sudo \
  && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
  && chmod 0440 /etc/sudoers.d/$USERNAME

RUN chown -R $USERNAME /usr/bin/geckodriver

USER $USERNAME
