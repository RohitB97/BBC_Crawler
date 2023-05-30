#! /bin/bash 

sudo apt-get update
sudo apt-get install -y firefox
wget https://github.com/mozilla/geckodriver/releases/download/v0.32.2/geckodriver-v0.32.2-linux64.tar.gz
tar -xvzf geckodriver*
rm geckodriver-v0.32.2-linux64.tar.gz
pip install selenium