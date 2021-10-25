import logging
import os
import os.path
import sys
import subprocess

from charmhelpers.fetch import (
    apt_install, add_source, apt_update, add_source)
from charmhelpers.core.host import (
    mkdir, symlink, write_file)
from subprocess import check_call, check_output
from charmhelpers.core.templating import render

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
               "runit-systemd", "libkrb5-dev", "libpq-dev"]
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
    
    logger.debug("download ruby")
    if not os.path.isfile("/tmp/ruby/ruby-2.7.4.tar.gz"):
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp/ruby ;"
            "curl --remote-name --progress-bar https://cache.ruby-lang.org/pub/ruby/2.7/ruby-2.7.4.tar.gz"
        ]
        check_output(cmd)

    logger.debug("extract ruby")
    if not os.path.isfile("/tmp/ruby/ruby-2.7.4"):
        # extract ruby
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp/ruby ;"
            "echo '3043099089608859fc8cce7f9fdccaa1f53a462457e3838ec3b25a7d609fbc5b ruby-2.7.4.tar.gz' | sha256sum -c - && tar xzf ruby-2.7.4.tar.gz"
        ]
        check_output(cmd)

    logger.debug("build and install ruby")
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

# 3. Go
def install_go():
    logger.info("Install go")
    # remove former Go installation folder
    if os.path.exists("/usr/local/go"):
        cmd = ["sudo", "rm", "-rf", "/usr/local/go"]
        check_output(cmd)
    # download Go
    if not os.path.isfile("/tmp/go1.16.9.linux-amd64.tar.gz"):
        cmd = [
            "/bin/bash", "-c",
            "set -o pipefail ;"
            "cd /tmp ;"
            "curl --remote-name --progress-bar https://dl.google.com/go/go1.16.9.linux-amd64.tar.gz ;"
        ]
        check_output(cmd)
    # Extract Go distribution
    cmd = [
        "/bin/bash", "-c",
        "set -o pipefail ;"
        "echo 'd2c095c95f63c2a3ef961000e0ecb9d81d5c68b6ece176e2a8a2db82dc02931c  /tmp/go1.16.9.linux-amd64.tar.gz' | shasum -a256 -c - && "
        "sudo tar -C /usr/local -xzf /tmp/go1.16.9.linux-amd64.tar.gz ;"
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

# 7. Redis
def install_redis():
    logger.info("Install redis")
    apt_install(["redis"])
    mkdir("/var/run/redis", owner="redis", group="redis", perms=0o755)
    content = "d  /var/run/redis  0755  redis  redis  10d  -\n"
    write_file("/etc/tmpfiles.d/redis.conf", content, perms=0o644)
    # Add git to the redis group
    check_output(["sudo", "usermod", "-aG", "redis", "git"])

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
    
    # Install Gems

    # Notice: libpq-dev package is required for the pg 1.2.3 gem
    logger.debug("Install Gems")
    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo -u git -H bundle config set --local deployment 'true' ;"
        "sudo -u git -H bundle config set --local without 'development test mysql aws kerberos' ;"
        "sudo -u git -H bundle install ;"
    ]
    check_output(cmd)

    # Install GitLab Shell
    logger.debug("Install GitLab Shell")
    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo -u git -H bundle exec rake gitlab:shell:install RAILS_ENV=production ;"
    ]
    check_output(cmd)

    # Install GitLab Workhorse
    logger.debug("Install GitLab Workhorse")
    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo -u git -H bundle exec rake \"gitlab:workhorse:install[/home/git/gitlab-workhorse]\" RAILS_ENV=production ;"
    ]
    check_output(cmd)

    # Install GitLab Pages
    logger.debug("Install GitLab Pages")
    if not os.path.exists("/home/git/gitlab-pages"):
        cmd = [
            "/bin/bash", "-c",
            "cd /home/git ;"
            "sudo -u git -H git clone https://gitlab.com/gitlab-org/gitlab-pages.git ;"
            "cd gitlab-pages ;"
            "sudo -u git -H git checkout v$(</home/git/gitlab/GITLAB_PAGES_VERSION) ;"
            "sudo -u git -H make"
        ]
        check_output(cmd)

    # Install Gitaly
    logger.debug("Install Gitaly")
    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo -u git -H bundle exec rake \"gitlab:gitaly:install[/home/git/gitaly,/home/git/repositories]\" RAILS_ENV=production ;"
        "sudo chmod 0700 /home/git/gitlab/tmp/sockets/private ;"
        "sudo chown git /home/git/gitlab/tmp/sockets/private ;"
    ]

    logger.debug("Render gitaly system service")
    config_path = "/etc/systemd/system/gitaly.service"
    config_template = '14-3-stable/gitaly.service.j2'
    context = { }
    render(config_template, config_path, context, perms=0o644,
            owner='root', group='root')

    check_output(cmd)


# 9. Nginx
def install_nginx():
    logger.info("Install nginx")
    apt_install(["nginx"])
    # create gitlab configuration symlink if not present
    if not os.path.exists("/etc/nginx/sites-enabled/gitlab"):
        symlink("/etc/nginx/sites-available/gitlab", "/etc/nginx/sites-enabled/gitlab")


def bootstrap_gitlab():
    # Install Gitaly
    logger.debug("Bootstrap gitlab")

    # cleanup redis
    cmd = ["redis-cli", "-s", "/var/run/redis/redis.sock", "flushall"]
    check_output(cmd)

    # setup gitlab
    cmd = [
        "/bin/bash", "-c",
        "cd /home/git/gitlab ;"
        "sudo -u git -H DISABLE_DATABASE_ENVIRONMENT_CHECK=1 bundle exec rake gitlab:setup RAILS_ENV=production GITLAB_ROOT_PASSWORD=s3cr3tpassw0rd GITLAB_ROOT_EMAIL=admin@example.com force=yes ;"
    ]
    try:
         p = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        logger.debug(e.stderr)
        raise


