### 

Setting up selenium on linux ubuntu is faster with firefox geckodriver use bellow:

```
#!/bin/bash
if [ ! -f "geckodriver.tar.gz" ]; then # only if not downloaded yet
    wget -O geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz
    tar -xvf geckodriver.tar.gz
    rm geckodriver.tar.gz
fi
sudo mv geckodriver /usr/bin/
sudo chmod +x /usr/bin/geckodriver
```
