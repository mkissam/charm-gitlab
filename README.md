# GitLab Operator Charm

## Description

This machine charm deploys the gitlab server into bare-machine, virtual-machine
or lxd container. The charm supports the 14.3 stable branch of GitLab.

## Usage

```
$ juju deploy ./gitlab-operator.charm --series focal --to lxd:0 gitlab-server
```

## Configuration options

### fqdn

GitLab server FQDN, like gitlab.yourdomain.tld

### email_from

Sender address of GitLab email notifications

### email_display_name

Sender display name of GitLab email notifications

### email_reply_to

GitLab email notification reply address

### email_subject_suffix

The suffix of notification email subjects

## Developing

The GitLab deployment is following the GitLab source based installation process.
Sets up the following environments and frameworks:
- development packages and prerequisites
- ruby 2.7.4
- go 1.15.12
- nodejs 14
- git from gitaly repository (14.3 stable branch)


Create and activate a virtualenv with the development requirements:

```
$ virtualenv -p python3 venv
$ source venv/bin/activate
$ pip install -r requirements-dev.txt
```


## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests
