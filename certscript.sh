openssl req -newkey rsa:4096 -x509 -days 825 -sha256 -nodes \
    -subj "/CN=34.29.65.235" \
    -addext "subjectAltName = IP:34.29.65.235" \
    -keyout server.key -out server.crt
