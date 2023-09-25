FROM alpine:3.18.3@sha256:7144f7bab3d4c2648d7e59409f15ec52a18006a128c733fcff20d3a4a54ba44a
RUN apk update && apk add curl jq bash pwgen openssh-client envsubst apache2-utils python3 py3-pip python3-dev build-base
ARG KUBECTL_VERSION=v1.26.8
RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl \
    && chmod +x ./kubectl \
    && mv ./kubectl /usr/local/bin/kubectl
ARG HELM_VERSION=v3.12.0
RUN curl -L https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz | tar zxv -C /tmp && mv /tmp/linux-amd64/helm /usr/local/bin/helm && rm -rf /tmp/linux-amd64
RUN echo "unknown:x:999:999:Unknown User:/nonexistent:/usr/sbin/nologin" >> /etc/passwd
COPY requirements.txt /srv/requirements.txt
RUN pip install -r /srv/requirements.txt
COPY setup.py /srv/
COPY uumpa_argocd_plugin /srv/uumpa_argocd_plugin
RUN pip install -e /srv
