import socket
import requests
import os
import subprocess
from dotenv import load_dotenv

def check_local_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def get_public_ip():
    try:
        return requests.get('https://api.ipify.org', timeout=5).text
    except:
        return "Unknown"

def check_dns(domain):
    try:
        return socket.gethostbyname(domain)
    except:
        return None

def main():
    load_dotenv()
    print("=== FlowerBot Connectivity Diagnostic ===")
    
    # 1. Local Binding
    port = 5000
    if check_local_port(port):
        print(f"[SUCCESS] Bot is listening locally on port {port}.")
    else:
        print(f"[ERROR] Bot is NOT listening on port {port}. Is the bot running?")

    # 2. Public IP
    public_ip = get_public_ip()
    print(f"[INFO] Your Public IP is: {public_ip}")

    # 3. DNS Resolution
    branding = "flowerbot.gg"
    dns_ip = check_dns(branding)
    if dns_ip:
        if dns_ip == public_ip:
            print(f"[SUCCESS] {branding} correctly points to your IP {public_ip}.")
        else:
            print(f"[WARNING] {branding} points to {dns_ip}, but your IP is {public_ip}.")
    else:
        print(f"[ERROR] {branding} does not resolve to any IP address yet.")

    # 4. Redirect URI
    redirect_uri = os.getenv('DISCORD_REDIRECT_URI')
    print(f"[INFO] Configured Redirect URI: {redirect_uri}")
    
    if branding not in redirect_uri and "localhost" not in redirect_uri:
        print("[WARNING] Your Redirect URI does not match your branding domain.")

    print("\n=== Troubleshooting Steps ===")
    print("1. DNS: Log in to your domain provider and add an A Record for '@' pointing to " + public_ip)
    print("2. Port Forwarding: In your router, forward TCP Port 5000 to your local machine IP.")
    print("3. Discord Portal: Ensure " + str(redirect_uri) + " is added to your OAuth2 Redirects in the Discord Developer Portal.")

if __name__ == "__main__":
    main()
