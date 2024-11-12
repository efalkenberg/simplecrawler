# simplecrawler
A basic web crawler


Default crawl (macOS Chrome)
```
python crawler.py <your_domain>`
```

Crawl as Android
```
python crawler.py <your_domain> --enable_android \
                                --disable_chrome_macos
```
Crawl as iOS
```
python crawler.py <your_domain> --enable_ios \
                                --disable_chrome_macos
```

Crawl as Desktop, Android AND iOS
```
python crawler.py <your_domain> --enable_android \
                                --enable_ios
```
