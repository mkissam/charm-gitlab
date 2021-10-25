#!/usr/bin/env python3
# Copyright 2021 Márton Kiss
# See LICENSE file for licensing details.

import logging
import subprocess
import sys
sys.path.append('lib')  # noqa: E402

from charmhelpers.core.templating import render
from charmhelpers.core.host import (
    service,
    service_running,
    service_start
)
from gitlab_helpers import gitlab

from ops.charm import CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
)
from ops.framework import StoredState
import ops.lib

pgsql = ops.lib.use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")

logger = logging.getLogger(__name__)


class GitlabServerCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(installed=False, bootstrapped=False,
                                db_conn_str=None, db_uri=None, db_ro_uris=[])

        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.config_changed, self.on_config_changed)

        self.db = pgsql.PostgreSQLClient(self, 'db')  # 'db' relation in metadata.yaml
        self.framework.observe(self.db.on.database_relation_joined, self._on_database_relation_joined)
        self.framework.observe(self.db.on.master_changed, self._on_master_changed)
        self.framework.observe(self.db.on.standby_changed, self._on_standby_changed)

    
    def on_install(self, event):
        self.model.unit.status = MaintenanceStatus('Installing gitlab server')        
        gitlab.install_packages_and_dependencies()
        gitlab.install_ruby()
        gitlab.install_go()
        gitlab.install_node()
        gitlab.create_system_user()
        gitlab.install_redis()
        gitlab.install_gitlab()
        gitlab.install_nginx()
        self._stored.installed = True
        self.model.unit.status = BlockedStatus('Waiting for database relation')
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
        if not self._stored.installed:
            logger.debug("Skipping configuration hook as the site is not installed yet.")
            return
        self._render_redis_configuration()
        self._render_gitlab_configuration()
        self._render_secrets_configuration()
        self._render_gitlab_redis_configuration()
        self._render_puma_configuration()
        self._render_database_configuration()
        self._render_nginx_configuration()

        # restart services to pick up configuration changes

        logger.info("Restart services")
        logger.debug("Restart redis service")
        service("restart", "redis")

        if not self._stored.db_conn_str and not self._stored.bootstrapped:
            self.model.unit.status = BlockedStatus('Waiting for database relation')

        if self._stored.db_conn_str and not self._stored.bootstrapped:
            self.model.unit.status = MaintenanceStatus('Bootstrapping gitlab server')
            logger.debug("Bootstrap Gitlab Database")
            logger.debug("ensure gitaly service is running")
            if not service_running("gitaly"):
                started = service_start("gitaly")
            logger.debug("pgsql db conn = {}".format(self._stored.db_conn_str))
            try:
                gitlab.bootstrap_gitlab()
            except subprocess.CalledProcessError as e:
                logger.error("Failed to execute rake gitlab:setup")
                raise RuntimeError('Failed to bootstrap gitlab')
            self._stored.bootstrapped = True
            self.model.unit.status = ActiveStatus('Ready')


    def _render_gitlab_configuration(self):
        logger.debug("Render gitlab configuration")
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

    def _render_redis_configuration(self):
        logger.debug("Render redis configuration")
        config_path = "/etc/redis/redis.conf"
        config_template = '14-3-stable/redis.conf.j2'
        context = {  }
        render(config_template, config_path, context, perms=0o640,
              owner='redis', group='redis')

    def _render_secrets_configuration(self):
        logger.debug("Render secrets configuration")
        config_path = "/home/git/gitlab/config/secrets.yml"
        config_template = '14-3-stable/secrets.yml.j2'
        context = { }
        render(config_template, config_path, context, perms=0o755,
              owner='git', group='git')

    def _render_gitlab_redis_configuration(self):
        logger.debug("Render gitlab redis configuration")
        config_path = "/home/git/gitlab/config/resque.yml"
        config_template = '14-3-stable/resque.yml.j2'
        context = { }
        render(config_template, config_path, context, perms=0o755,
              owner='git', group='git')

    def _render_puma_configuration(self):
        logger.debug("Render puma gitlab configuration")
        config_path = "/home/git/gitlab/config/puma.rb"
        config_template = '14-3-stable/puma.rb.j2'
        context = { }
        render(config_template, config_path, context, perms=0o755,
              owner='git', group='git')

    def _render_database_configuration(self):
        logger.debug("Render database configuration")
        config_path = "/home/git/gitlab/config/database.yml"
        config_template = '14-3-stable/database.yml.j2'
        context = { }
        if self._stored.db_conn_str:
            kv = dict(item.split("=") for item in self._stored.db_conn_str.split(" "))
            # context.update(res)
            context["database"] = kv["dbname"]
            context["username"] = kv["user"]
            context["password"] = kv["password"]
            context["db_host"] = kv["host"]
            context["db_port"] = kv["port"]
            # TODO: use port in database template

        render(config_template, config_path, context, perms=0o755,
              owner='git', group='git')

    def _render_nginx_configuration(self):
        logger.debug("Render nginx configuration")
        config_path = "/etc/nginx/sites-available/gitlab"
        config_template = '14-3-stable/nginx-gitlab.j2'
        context = {
            "fqdn": "localhost"
        }
        render(config_template, config_path, context, perms=0o755)

    def _on_database_relation_joined(self, event: pgsql.DatabaseRelationJoinedEvent):
        logger.debug("_on_database_relation_joined()")
        if self.model.unit.is_leader():
            # Provide requirements to the PostgreSQL server.
            event.database = 'gitlab-server'
            event.extensions = ['pg_trgm', 'btree_gist']
        elif event.database != 'gitlab-server':
            # Leader has not yet set requirements. Defer, incase this unit
            # becomes leader and needs to perform that operation.
            event.defer()
            return

    def _on_master_changed(self, event: pgsql.MasterChangedEvent):
        logger.debug("_on_master_changed()")
        if event.database != 'gitlab-server':
            # Leader has not yet set requirements. Wait until next event,
            # or risk connecting to an incorrect database.
            return
        
        # The connection to the primary database has been created,
        # changed or removed. More specific events are available, but
        # most charms will find it easier to just handle the Changed
        # events. event.master is None if the master database is not
        # available, or a pgsql.ConnectionString instance.
        self._stored.db_conn_str = None if event.master is None else event.master.conn_str
        self._stored.db_uri = None if event.master is None else event.master.uri

        # You probably want to emit an event here or call a setup routine to
        # do something useful with the libpq connection string or URI now they
        # are available.
        self.on_config_changed(event)

    def _on_standby_changed(self, event: pgsql.StandbyChangedEvent):
        logger.debug("_on_standby_changed()")
        if event.database != 'gitlab-server':
            # Leader has not yet set requirements. Wait until next event,
            # or risk connecting to an incorrect database.
            return

        # Charms needing access to the hot standby databases can get
        # their connection details here. Applications can scale out
        # horizontally if they can make use of the read only hot
        # standby replica databases, rather than only use the single
        # master. event.stanbys will be an empty list if no hot standby
        # databases are available.
        self._stored.db_ro_uris = [c.uri for c in event.standbys]



if __name__ == "__main__":
    main(GitlabServerCharm)
