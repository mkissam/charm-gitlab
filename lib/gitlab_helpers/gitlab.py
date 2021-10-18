import logging
import os
import os.path

from charmhelpers.fetch import (
    apt_install, add_source, apt_update, add_source)
from subprocess import check_call, check_output

logger = logging.getLogger(__name__)

# 1. Packages and dependencies
def install_packages_and_dependencies():
    logger.info("Install packages and dependencies")
    apt_update()

    # Build dependencies
    packages = ["build-essential", "zlib1g-dev", "libyaml-dev", "libssl-dev",
               "libgdbm-dev", "libre2-dev", "libreadline-dev", "libncurses5-dev",
               "libffi-dev", "curl", "openssh-server", "libxml2-dev",
               "libxslt-dev", "libcurl4-openssl-dev", "libicu-dev", "logrotate",
               "rsync", "python-docutils", "pkg-config", "cmake",
               "runit-systemd", "libkrb5-dev"]
    apt_install(packages)

    # Git
    packages = ["libcurl4-openssl-dev", "libexpat1-dev", "gettext", "libz-dev",
               "libssl-dev", "libpcre2-dev", "build-essential", "git-core"]
    apt_install(packages)

    # clone and build git only if it was not built before
    if not os.path.isfile("/usr/local/bin/git"):
        # clone git repository
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "git clone https://gitlab.com/gitlab-org/gitaly.git -b {} /tmp/gitaly"
            "".format("14-3-stable")
        ]
        check_output(cmd)

        # build git to /usr/local
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp/gitaly ;"
            "sudo make git GIT_PREFIX=/usr/local"
        ]
        check_output(cmd)

    # GraphicsMagick
    packages = ["graphicsmagick"]
    apt_install(packages)

    # Mail server
    packages = ["postfix"]
    apt_install(packages)

    # Exiftool
    packages = ["libimage-exiftool-perl"]
    apt_install(packages)


# 2. Ruby
def install_ruby():
    logger.info("Install ruby")
    ruby_tmpdir = "/tmp/ruby"
    if not os.path.exists(ruby_tmpdir):
        os.mkdir(ruby_tmpdir)
    
    logger.info("DEBUG: download ruby")
    if not os.path.isfile("/tmp/ruby/ruby-2.7.4.tar.gz"):
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp/ruby ;"
            "curl --remote-name --progress-bar https://cache.ruby-lang.org/pub/ruby/2.7/ruby-2.7.4.tar.gz"
        ]
        check_output(cmd)

    logger.info("DEBUG: extract ruby")
    if not os.path.isfile("/tmp/ruby/ruby-2.7.4"):
        # extract ruby
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp/ruby ;"
            "echo '3043099089608859fc8cce7f9fdccaa1f53a462457e3838ec3b25a7d609fbc5b ruby-2.7.4.tar.gz' | sha256sum -c - && tar xzf ruby-2.7.4.tar.gz"
        ]
        check_output(cmd)

    logger.info("DEBUG: build and install ruby")
    # build ruby
    if not os.path.isfile("/usr/local/bin/ruby"):
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp/ruby/ruby-2.7.4 ;"
            "./configure --disable-install-rdoc --enable-shared ;"
            "make ;"
            "sudo make install"
        ]
        check_output(cmd)
    logger.info("DEBUG: done")

# 3. Go
def install_go():
    logger.info("Install go")
    # remove former Go installation folder
    if not os.path.exists("/usr/local/go"):
        cmd = ["sudo", "rm", "-rf", "/usr/local/go"]
        check_output(cmd)
    # download Go
    if not os.path.isfile("/tmp/go1.15.12.linux-amd64.tar.gz"):
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp ;"
            "curl --remote-name --progress-bar https://dl.google.com/go/go1.15.12.linux-amd64.tar.gz ;"
        ]
        check_output(cmd)
    # Extract Go distribution
    cmd = [
        "/bin/bash", "-c",
        "set -o pipefail ;"
        "echo 'bbdb935699e0b24d90e2451346da76121b2412d30930eabcd80907c230d098b7  /tmp/go1.15.12.linux-amd64.tar.gz' | shasum -a256 -c - && "
        "sudo tar -C /usr/local -xzf /tmp/go1.15.12.linux-amd64.tar.gz ;"
        "sudo ln -sf /usr/local/go/bin/{go,godoc,gofmt} /usr/local/bin/ ;"
    ]
    check_output(cmd)

# 4. Node
def install_node():
    logger.info("Install node")
    if not os.path.isfile("/tmp/setup_14.x"):
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp ;"
            "curl --location https://deb.nodesource.com/setup_14.x > /tmp/setup_14.x ;"
            "cat /tmp/setup_14.x | sudo bash -"
        ]
        check_output(cmd)
    apt_install(["nodejs"])

    cmd = [
        "/bin/bash", "-c",
        "set -o pipefail ;"
        "npm install --global yarn ;"
    ]
    check_output(cmd)

# 5. System users
def create_system_user():
    logger.info("Create system user")
    # Notice: would be great to check the presence of the git user.
    if not os.path.exists("/home/git"):
        cmd = [
            "sudo", "adduser", "--disabled-login", "--gecos", "'GitLab'","git"
        ]
        check_output(cmd)

# 8. GitLab
def install_gitlab():
    logger.info("Install gitlab")
    # Clone gitlab repository
    if not os.path.exists("/home/git/gitlab"):
        # clone git repository
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /home/git ;"
            "sudo -u git -H git clone https://gitlab.com/gitlab-org/gitlab-foss.git -b {} gitlab"
            "".format("14-3-stable")
        ]
        check_output(cmd)

    # TODO: create from template: /home/git/gitlab/config/gitlab.yml
    # TODO: generate secrets: /home/git/gitlab/config/secrets.yml

    # Make sure GitLab can write to the log/ and tmp/ directories
    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo chown -R git log/ ;"
        "sudo chmod -R u+rwX,go-w log/ ;"
        "sudo chmod -R u+rwX tmp/ ;"
    ]
    check_output(cmd)

    # Make sure GitLab can write to the tmp/pids/ and tmp/sockets/ directories
    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo chmod -R u+rwX tmp/pids/ ;"
        "sudo chmod -R u+rwX tmp/sockets/ ;"
    ]
    check_output(cmd)

    # Create the public/uploads/ directory
    if not os.path.exists("/home/git/gitlab/public/uploads"):
        cmd = [
            "/bin/bash", "-c",
            "cd /home/git/gitlab ;"
            "sudo -u git -H mkdir -p public/uploads/ ;"
            "sudo chmod 0700 public/uploads ;"
        ]
        check_output(cmd)

    # Change the permissions of the directory where CI job logs are stored
    # Change the permissions of the directory where CI artifacts are stored
    # Change the permissions of the directory where GitLab Pages are stored
    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo chmod -R u+rwX builds/ ;"
        "sudo chmod -R u+rwX shared/artifacts/ ;"
        "sudo chmod -R ug+rwX shared/pages/ ;"
    ]
    check_output(cmd)

    # TODO: create from template: /home/git/gitlab/config/puma.rb

    # Configure Git global settings for git user
    # 'autocrlf' is needed for the web editor
    # Disable 'git gc --auto' because GitLab already runs 'git gc' when needed
    # Enable packfile bitmaps
    # Enable push options
    # Enable fsyncObjectFiles to reduce risk of repository corruption if the server crashes

    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo -u git -H git config --global core.autocrlf input ;"
        "sudo -u git -H git config --global gc.auto 0 ;"
        "sudo -u git -H git config --global repack.writeBitmaps true ;"
        "sudo -u git -H git config --global receive.advertisePushOptions true ;"
        "sudo -u git -H git config --global core.fsyncObjectFiles true ;"
    ]
    check_output(cmd)

    # Configure Redis connection settings
    # TODO: create from template: /home/git/gitlab/config/resque.yml
    # return

# 9. Nginx
def install_nginx():
    logger.info("Install nginx")
    apt_install(["nginx"])
    # create gitlab configuration symlink
    cmd = [
        "/bin/bash", "-c",
        "sudo ln -s /etc/nginx/sites-available/gitlab /etc/nginx/sites-enabled/gitlab;"
    ]
    check_output(cmd)

