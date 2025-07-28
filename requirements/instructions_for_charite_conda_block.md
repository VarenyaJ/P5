### Check for Blockages
Ensure ´https://repo.anaconda.com/´ is not blocked by your IT/ISP/DNS provider
    -   e.g. "UnavailableInvalidChannel: HTTP 403 FORBIDDEN for channel pkgs/main <https://repo.anaconda.com/pkgs/main>"

If you work at a university like the Charité, you should probably switch to the "Eduroam" wireless network to install conda, and then you can switch back to your preferred wireless/LAN network for pip installation and use of this package

You may need to trust your organization's CA:
```bash
# Install/update certifi in your base environment. Also ensure `/etc/ssl/certs/` or your system store is used:
conda install -n base certifi

# Configure conda to trust a custom CA **if need be**:
conda config --set ssl_verify /path/to/your/cacert.pem

# Disable SSL verification (not recommended permanently):
conda config --set ssl_verify false

# Use curl/openssl to test connectivity and certificate chain:
openssl s_client -showcerts -connect repo.anaconda.com:443

# Clean any cached metadata:
conda clean --all

# Re-run your env creation:
conda env create -f requirements/environment.yml -n p5

# If that works, you can later re-enable SSL verification with:
conda config --set ssl_verify true



# Alternative (safer) approach: point Conda at Python's certifi bundle instead of turning off verification globally:
# Install certifi in your base env (if not already)
conda install -n base certifi

# Then export this in your shell before running conda:
export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")

# Now retry:
conda env create -f requirements/environment.yml -n p5


# Check Channels and Sources for "~/.condarc":
conda config --add channels conda-forge
conda config --set channel_priority strict
conda config --show channels
conda config --show-sources


# To avoid the "~/conda.rc" mess, you could:
# 1) Create the env with Python only, from conda-forge:
conda create -n p5 python=3.13 -c conda-forge

# 2) Activate and pip-install your requirements:
conda activate p5
pip install -r requirements.txt -r requirements_scripts.txt -r requirements_test.txt
```


