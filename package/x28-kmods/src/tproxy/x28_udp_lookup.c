// The stock kernel was built without TPROXY and socket, so net/ipv{4,6}/udp.c never exported these two. Same bodies as upstream 4.19.
#include <linux/module.h>
#include <net/udp.h>
#include <net/ipv6.h>

struct sock *udp4_lib_lookup(struct net *net, __be32 saddr, __be16 sport,
			     __be32 daddr, __be16 dport, int dif)
{
	struct sock *sk;

	sk = __udp4_lib_lookup(net, saddr, sport, daddr, dport,
			       dif, 0, &udp_table, NULL);
	if (sk && !refcount_inc_not_zero(&sk->sk_refcnt))
		sk = NULL;
	return sk;
}
EXPORT_SYMBOL_GPL(udp4_lib_lookup);

struct sock *udp6_lib_lookup(struct net *net, const struct in6_addr *saddr, __be16 sport,
			     const struct in6_addr *daddr, __be16 dport, int dif)
{
	struct sock *sk;

	sk = __udp6_lib_lookup(net, saddr, sport, daddr, dport,
			       dif, 0, &udp_table, NULL);
	if (sk && !refcount_inc_not_zero(&sk->sk_refcnt))
		sk = NULL;
	return sk;
}
EXPORT_SYMBOL_GPL(udp6_lib_lookup);

MODULE_LICENSE("GPL");
