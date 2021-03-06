tls-terminator
==============

Configures nginx as TLS terminator for a http(s) backend.

Conceptually this is organized around the following terms:
- **site**: An internet-facing (or internal) https endpoint. This is grouped by hostname,
  thus `api.example.com` and `example.com` would be two different sites.
- **backend**: Each site has one or more backends, grouped by url prefix. Thus
  `example.com` and `example.com/docs` could be two different backends for a given site.
- **upstreams**: Each backend has one or more upstreams, which is the service that actually
  generates the response for a given request. This is usually another http(s) url.

By default the HTTP Host header will be set to the same as the upstream if a single
upstream is given, ie if the only upstream is `example.herokuapp.com` the Host header will
be `example.herokuapp.com`. If there are multiple upstreams the default Host header will
be that of the site. The latter behavior can also be set for a single upstream by setting
`upstream_hostname` to `site` in the backend or site config. `upstream_hostname` can also
be set to any arbitrary value that will be used for all upstreams.

The state will add the following security headers by default:
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` Ensures later requests are made over https too.
- `X-Frame-Options: DENY` Prevents click-jacking by preventing the page from being framed.
- `X-Xss-Protection: 1; mode=block` Turns on the browser's built-in XSS protection.
- `X-Content-Type-Options: nosniff` Disables mime-type sniffing in browsers.

There are some more headers that the upstream should set since they are very site specific, like
`Content-Security-Policy`, `Referrer-Policy` and `Feature-Policy`. If you can't configure the
headers on the backend you can configure them both globally on the tls-terminator (convenient for
`Expect-CT` where you just need to set a report uri) or per site (`Referrer-Policy`) through the
`add_headers` key, or per backend. This also enables overriding the defaults mentioned above. The
default headers will only be added if the header isn't already set by the upstream.

You can remove the default headers or headers set globally by setting them to an empty string.

Sample pillar config:

```yaml
tls-terminator:
    example.com:
        backend: https://example-app.herokuapp.com
        cert: |
            ---BEGIN CERTIFICATE----
            <snip>
            ---END CERTIFICATE------
        key: |
            ---BEGIN PRIVATE KEY----
            <snip>
            ---END PRIVATE KEY------
```

`cert` and `key` is only needed if you want to override the nginx default cert set through
`nginx:default_cert`.

If you want to have different backends for different URLs, you can set the `backends` parameter
instead:

```yaml
tls-terminator:
    otherexample.com:
        backends:
            /: https://example-app.herokuapp.com
            /api:
                upstreams:
                    - http://10.10.10.10:8000 weight=5
                    - http://10.10.10.11:8000
                    - http://10.10.10.12:8000 backup
                upstream_least_conn: True
                upstream_keepalive: 32
```

A HTTPS backend is validated against the system trust root if no explicit trust root is given. To
set a trust root:

```yaml
tls-terminator:
    example.com:
        backends:
            /:
                upstream: https://example-app.herokuapp.com
                upstream_trust_root: |
                    <upstream-cert>
```

As you might have guessed, `backend: <url>` is just a convenient alias for
`backends: {"/": {"upstream": <url>}}`.

You can add extra location blocks if needed:

```yaml
tls-terminator:
    example.com:
        backend: https://example-app.herokuapp.com
        extra_locations:
            /.well-known/assetlinks.json: |
                return 200 '[{ "namespace": "android_app",
                   "package_name": "org.digitalassetlinks.example",
                   "sha256_cert_fingerprints":
                     ["14:6D:E9:83:C5:73:06:50:D8:EE:B9:95:2F:34:FC:64:16:"
                      "A0:83:42:E6:1D:BE:A8:8A:04:96:B2:3F:CF:44:E5"]}]';
```

You can also add a redirect to another site, in this case `www.example.com/foo` will 301
to `https://example.com/foo`, while `other.example.com/foo` will 307 to `https://example.com`.

```yaml
tls-terminator:
    www.example.com:
        redirect: https://example.com

    other.example.com:
        redirect:
            status: 307
            url: https://example.com
            include_uri: False

    example.com:
        backend: https://example-app.herokuapp.com
```


To set up rate-limiting:

```yaml
tls-terminator:
    example.com:
        rate_limit:
            zones:
                default:
                    key: $cookie_session
                    size: 10m
                    rate: 1r/s
                sensitive:
                    rate: 6r/m
                    # key defaults to $binary_remote_addr when unset
                    # size defaults to 1m when unset
            backends:
                /:
                    zone: default
                    burst: 3
                /login:
                    zone: sensitive
                    burst: 4
        backend: http://127.0.0.1:5000
```

Each backend defaults to setting the `nodelay` flag, this can be turned off per backend by setting
`nodelay: False`.


When forwarding requests there are a couple common errors that can originate at the tls-terminator,
like 502 (Bad Gateway), 504 (Gateway Timeout) and 429 (Too Many Requests, only when setting rate
limits). The state includes default error pages for these conditions, but you can also override
these if you want to put special styling on them. They have to be a single page of html, and can be
set both globally for all sites in the state or on a per-site basis:

```yaml
tls-terminator:
    error_pages:
        429: |
            <!doctype html>
            <title>My custom rate limited error page</title>
            <p>Your requests to {{ site }} have been rate limited</p>
    example.com:
        backend: http://127.0.0.1:5000
        error_pages:
            429: |
                <!doctype html>
                <title>Too many requests to example.com</title>
```

The error page can be a jinja template, and will receive the name of the site in a variable `site`
that can be used to customize the page. The page defaults to being served as html, the content type
can be overridden like this:

```yaml
tls-terminator:
    api.example.com:
        error_pages:
            504:
                content_type: application/json
                content: |
                    {
                        "error": {
                            "status": 504,
                            "message": "Gateway timeout",
                        }
                    }
```

The custom error pages are only used for errors originating from the tls-terminator, if the upstream
returns any of the errors itself the response is sent unmodified to the client.

If you're running a nested setup where this tls-terminator isn't public facing, but is sitting
behind another instance that is, you can set the flag `nested: True` to disable caching, use the
`X-Request-Id` from the outer instance, and not add any security headers:

```yaml
tls-terminator:
    internal.example.com:
        backend: http://127.0.0.1:5000
        nested: True
```

To require clients to authenticate themselves with a valid TLS cert, set the certificate they
should be validated against:

```yaml
tls-terminator:
    example.com:
        backend: http://127.0.0.1:5000
        client_cert: |
            -----BEGIN CERTIFICATE-----
            foo
            -----END CERTIFICATE-----
```
