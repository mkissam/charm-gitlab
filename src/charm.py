#!/usr/bin/env python3
# Copyright 2021 Márton Kiss
# See LICENSE file for licensing details.

import logging
import sys
sys.path.append('lib')  # noqa: E402

from charmhelpers.core.templating import render
from gitlab_helpers import gitlab

from ops.charm import CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
)
from ops.framework import StoredState

logger = logging.getLogger(__name__)


class GitlabServerCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.fortune_action, self._on_fortune_action)
        self._stored.set_default(things=[])

    def _on_config_changed(self, _):
        current = self.config["thing"]
        if current not in self._stored.things:
            logger.debug("found a new thing: %r", current)
            self._stored.things.append(current)

    def _on_fortune_action(self, event):
        fail = event.params["fail"]
        if fail:
            event.fail(fail)
        else:
            event.set_results({"fortune": "A bug in the code is worth two in the documentation."})

    def on_install(self, event):
        self.model.unit.status = MaintenanceStatus('Installing gitlab server')        
        gitlab.install_packages_and_dependencies()
        gitlab.install_ruby()
        gitlab.install_go()
        gitlab.install_node()
        gitlab.create_system_user()
        gitlab.install_gitlab()
        gitlab.install_nginx()
        logger.info("Install hook finished.")

    def _on_config_changed(self, _):
        # current = self.config["thing"]
        # if current not in self._stored.things:
        #     logger.debug("found a new thing: %r", current)
        #     self._stored.things.append(current)
        return

    def _on_fortune_action(self, event):
        fail = event.params["fail"]
        if fail:
            event.fail(fail)
        else:
            event.set_results({"fortune": "A bug in the code is worth two in the documentation."})

    def on_config_changed(self, event):
        logger.info("Configuration changed")
        self._render_gitlab_configuration()
        self._render_secrets_configuration()
        self._render_redis_configuration()
        self._render_puma_configuration()
        self._render_database_configuration()
        self._render_nginx_configuration()

        # restart services to pick up configuration changes
        # TODO ^^^

    def _render_gitlab_configuration(self):
        logger.info("Render gitlab configuration")
        config_path = "/home/git/gitlab/config/gitlab.yml"
        config_template = '14-3-stable/gitlab.yml.j2'
        context = { 
            "fqdn": "localhost",
            "email_from": "example@example.com",
            "email_display_name": "GitLab",
            "email_reply_to": "noreply@example.com",
            "email_subject_suffix": ""
        }
        render(config_template, config_path, context, perms=0o755)

    def _render_secrets_configuration(self):
        logger.info("Render secrets configuration")
        config_path = "/home/git/gitlab/config/secrets.yml"
        config_template = '14-3-stable/secrets.yml.j2'
        context = { }
        render(config_template, config_path, context, perms=0o755)

    def _render_redis_configuration(self):
        logger.info("Render redis configuration")
        config_path = "/home/git/gitlab/config/resque.yml"
        config_template = '14-3-stable/resque.yml.j2'
        context = { }
        render(config_template, config_path, context, perms=0o755)

    def _render_puma_configuration(self):
        logger.info("Render puma gitlab configuration")
        config_path = "/home/git/gitlab/config/puma.rb"
        config_template = '14-3-stable/puma.rb.j2'
        context = { }
        render(config_template, config_path, context, perms=0o755)

    def _render_database_configuration(self):
        logger.info("Render database configuration")
        config_path = "/home/git/gitlab/config/database.yml"
        config_template = '14-3-stable/database.yml.j2'
        context = { }
        render(config_template, config_path, context, perms=0o755)

    def _render_nginx_configuration(self):
        logger.info("Render nginx configuration")
        config_path = "/etc/nginx/sites-available/gitlab"
        config_template = '14-3-stable/nginx-gitlab.j2'
        context = {
            "fqdn": "localhost"
        }
        render(config_template, config_path, context, perms=0o755)


if __name__ == "__main__":
    main(GitlabServerCharm)
