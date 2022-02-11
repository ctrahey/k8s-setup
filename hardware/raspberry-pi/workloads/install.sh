mkdir -p /etc/keepalived
mkdir -p /etc/haproxy
mkdir -p /etc/kubernetes/manifests
cp check_apiserver.sh /etc/keepalived/check_apiserver.sh
cp keepalived.conf /etc/keepalived/keepalived.conf
cp haproxy.cfg /etc/haproxy/haproxy.cfg
cp haproxy.yaml /etc/kubernetes/manifests/haproxy.yaml
cp keepalived.yaml /etc/kubernetes/manifests/keepalived.yaml
