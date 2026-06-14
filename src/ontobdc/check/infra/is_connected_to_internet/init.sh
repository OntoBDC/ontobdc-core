DESCRIPTION="Infra: Internet Connection"

check() {
    # Check using curl (HTTP/HTTPS) which usually works in Colab/Restricted environments
    # Try Google
    if curl -s --head --request GET http://www.google.com >/dev/null 2>&1; then
        return 0
    fi
    
    # Try PyPI (crucial for pip)
    if curl -s --head --request GET https://pypi.org >/dev/null 2>&1; then
        return 0
    fi

    # Fallback to python urllib (standard library)
    if python3 -c "import urllib.request; urllib.request.urlopen('http://www.google.com', timeout=3)" >/dev/null 2>&1; then
        return 0
    fi
    
    # Last resort: Ping (might fail in containers/Colab)
    if ping -c 1 -t 2 8.8.8.8 >/dev/null 2>&1; then
        return 0
    fi

    return 1
}

hotfix() {
    # Cannot really fix internet connection programmatically without sudo/network reset
    # But we can wait a moment and retry in case of transient failure
    echo "  ! Waiting 3s to retry connection..."
    sleep 3
    check
}

repair() {
    hotfix
}
