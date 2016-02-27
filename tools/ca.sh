#!/bin/bash

set -e

PKI_DIR=/tmp/ca

function new-root () {
    if [ $# -ne 1 ]; then
        stderr "usage: new-root <Name of new root>"
        exit 1
    fi

    local root_fqdn="$1"
    _create-new-ca-directory-structure "$root_fqdn"

    echo -n "Enter service name for this CA: "
    local service
    read -r service
    local private_key=$(_create-new-key)
    export OU="$service"
    export CA_FQDN="$root_fqdn"
    cat <<EOF
[INFO] Now we'll create the CSR.
EOF
    local csr=$(_openssl req -new \
                -key <(echo "$private_key") \
                -nodes)
    cat <<EOF
[INFO] We'll now write the private key for your new root CA to disk, which
       means we have to encrypt it first. Enter the key you want to encrypt
       it under.

       Hint: You can create strong keys by using "openssl rand -base64 30"
EOF
    echo -n "$private_key" \
    | encrypt_key_to_file "$PKI_DIR/ca/$root_fqdn/private/$root_fqdn.key"

    cat <<EOF
[INFO] We'll now self-sign our root certificate, enter the key you just created again.
EOF
    _openssl ca \
        -selfsign \
        -in <(echo "$csr") \
        -out "$PKI_DIR/certs/$root_fqdn.crt" \
        -extensions root_ca_ext \
        -days 7300 \
        -notext
}

function create-client-only-cert () {
    if [ $# -ne 2 ]; then
        stderr "usage: create-client-only-cert <fqdn-prefix for new server> <fqdn of desired CA>"
        exit 1
    fi
    create-cert-with-extension $@ client_only_ext
}

function create-server-only-cert () {
    if [ $# -ne 2 ]; then
        stderr "usage: create-server-only-cert <fqdn-prefix for new server> <fqdn of desired CA>"
        exit 1
    fi
    create-cert-with-extension $@ server_only_ext
}

function create-client-and-server-cert () {
    if [ $# -ne 2 ]; then
        stderr "usage: create-client-and-server-cert <fqdn-prefix for new server> <fqdn of desired CA>"
        exit 1
    fi
    create-cert-with-extension $@ client_and_server_ext
}

function revoke-cert () {
    if [ $# -ne 1 ]; then
        stderr "Usage: revoke-cert <fqdn of cert to revoke>"
        exit 1
    fi

    local ca_fqdn="$1"
    local cert_path="$PKI_DIR/certs/${ca_fqdn}.crt"

    if [ ! -f "$cert_path" ]; then
        echo "ERROR: Could not find certificate for $ca_fqdn, tried $cert_path"
        exit 1
    fi

    local cert_issuer=$(openssl x509 -noout -issuer -in "$cert_path")
    local issuer_dn=$(echo "$cert_issuer" | grep -Eo "/CN=[^/]+" | sed "s/\/CN=//")

    CA_FQDN="$issuer_dn" _openssl ca \
        -revoke "$cert_path"

    update-crl "$issuer_dn"
}

function update-crl () {
    if [ $# -ne 1 ]; then
        echo >&2 "Usage: update-crl <fqdn of CA>"
        exit 1
    fi

    local ca_fqdn="$1"
    CA_FQDN="$ca_fqdn" _openssl ca \
        -gencrl
}

function show-help () {
    echo "Usage: manage <func> [<args>]"
    echo
    echo "Functions:"
    echo "   new-root <fqdn-of-new-root-ca>"
    echo "   create-new-ca <fqdn-of-new-subca>"
    echo "   create-server-cert <FQDN of server>"
    echo "   sign-user-request <csr>"
    echo "   revoke-user <username>"
}

function create-cert-with-extension () {
    local ca_fqdn="$2"
    local server_fqdn="${1}.${ca_fqdn}"
    local extensions="$3"

    local private_key=$(_create-new-key)
    local cert_dn=$(cut -f6 "$PKI_DIR/ca/$ca_fqdn/db/db" | head -1)
    local organization=$(echo "$cert_dn" | grep -Eo "/O=[^/]+" | sed "s/\/O=//")
    local service=$(echo "$cert_dn" | grep -Eo "/OU=[^/]+" | sed "s/\/OU=//")

    local csr=$(SERVER_FQDN="$server_fqdn" O="$organization" OU="$service" openssl req \
                -new \
                -key <(echo "$private_key") \
                -config <(get-tls-server-openssl.cnf))

    CA_FQDN="$ca_fqdn" _openssl ca \
               -in <(echo "$csr") \
               -out "$PKI_DIR/certs/$server_fqdn.crt" \
               -extensions "$extensions" \
               -notext

    echo "$private_key"
}

function _create-new-ca-directory-structure () {
    local root="$1"
    mkdir -p $PKI_DIR/certs
    mkdir -p "$PKI_DIR/ca/$root/"{private,db}
    echo 01 > "$PKI_DIR/ca/$root/db/serial"
    echo 01 > "$PKI_DIR/ca/$root/db/crl.srl"
    touch "$PKI_DIR/ca/$root/db/db"
}

function _create-new-key () {
    openssl ecparam -name secp256k1 -genkey
}

function _openssl () {
    pushd "$PKI_DIR" >/dev/null 2>&1
    openssl $@ -config <(get-openssl.cnf)
    popd >/dev/null
}

function get-tls-server-openssl.cnf () {
    cat <<"EOF"
# This file is used by the openssl req command. The subjectAltName cannot be
# prompted for and must be specified in the SAN environment variable.

cn = ${ENV::SERVER_FQDN}
ou = ${ENV::OU}
o = ${ENV::O}

[ default ]
SAN                     = DNS:$cn    # Default value

[ req ]
encrypt_key             = no                    # Protect private key
default_md              = sha512                # MD to use
utf8                    = yes                   # Input is UTF-8
string_mask             = utf8only              # Emit UTF-8 strings
prompt                  = no                    # Prompt for DN
distinguished_name      = server_dn             # DN template
req_extensions          = server_reqext         # Desired extensions

[ server_dn ]
organizationName                = $o
organizationalUnitName          = $ou
commonName                      = $cn

[ server_reqext ]
keyUsage                = critical,digitalSignature,keyEncipherment
extendedKeyUsage        = serverAuth
subjectKeyIdentifier    = hash
subjectAltName          = DNS:$cn
EOF
}

function encrypt_key_to_file () {
    openssl pkcs8 \
        -v2 aes-256-cbc \
        -topk8 \
        -out "$1"
}

function stderr () {
    echo >&2 $@
}

function get-openssl.cnf () {
    cat <<"EOF"
organization            = "Megacool"
mode                    = root
OU                      = "Default service"
service                 = ${ENV::OU}
ca                      = ${ENV::CA_FQDN}              # CA name
dir                     = .                   # Top dir

# The next part of the configuration file is used by the openssl req command.
# It defines the CA's key pair, its DN, and the desired extensions for the CA
# certificate.

[ req ]
encrypt_key             = yes                   # Protect private key
default_md              = sha512                # MD to use
utf8                    = yes                   # Input is UTF-8
string_mask             = utf8only              # Emit UTF-8 strings
prompt                  = no                    # Don't prompt for DN
distinguished_name      = ca_dn                 # DN section
req_extensions          = ca_reqext             # Desired extensions

[ ca_dn ]
organizationName        = $organization
organizationalUnitName  = $service
commonName              = $ca

[ ca_reqext ]
keyUsage                = critical,keyCertSign,cRLSign
basicConstraints        = critical,CA:true
subjectKeyIdentifier    = hash

# The remainder of the configuration file is used by the openssl ca command.
# The CA section defines the locations of CA assets, as well as the policies
# applying to the CA.

[ ca ]
default_ca              = ${mode}_ca               # The default CA section

[ root_ca ]
certificate             = certs/$ca.crt       # The CA cert
private_key             = ca/$ca/private/$ca.key # CA private key
new_certs_dir           = ca/$ca           # Certificate archive
serial                  = ca/$ca/db/serial # Serial number file
crlnumber               = ca/$ca/db/crl.srl # CRL number file
database                = ca/$ca/db/db     # Index file
unique_subject          = no                    # Require unique subject
default_days            = 180                   # How long to certify for
default_md              = sha512                # MD to use
policy                  = match_pol             # Default naming policy
email_in_dn             = no                    # Add email to cert DN
preserve                = no                    # Keep passed DN ordering
name_opt                = ca_default            # Subject DN display options
cert_opt                = ca_default            # Certificate display options
copy_extensions         = copy                  # Copy extensions from CSR
default_crl_days        = 14                    # How long before next CRL
crl_extensions          = crl_ext               # CRL extensions

# Naming policies control which parts of a DN end up in the certificate and
# under what circumstances certification should be denied.

[ match_pol ]
organizationName        = match                 # Must match top-level org like "Megacool"
organizationalUnitName  = match                 # Service type must match (ie Public TLS terminator or Postgres)
commonName              = supplied              # Must be present

# Certificate extensions define what types of certificates the CA is able to
# create.

[ root_ca_ext ]
keyUsage                = critical,keyCertSign,cRLSign
basicConstraints        = critical,CA:true,pathlen:0
subjectKeyIdentifier    = hash
authorityKeyIdentifier  = keyid:always

[ server_only_ext ]
keyUsage                = critical,digitalSignature,keyEncipherment
extendedKeyUsage        = serverAuth
basicConstraints        = CA:false
subjectKeyIdentifier    = hash
authorityKeyIdentifier  = keyid:always

[ client_only_ext ]
keyUsage                = critical,digitalSignature,keyEncipherment
extendedKeyUsage        = clientAuth
basicConstraints        = CA:false
subjectKeyIdentifier    = hash
authorityKeyIdentifier  = keyid:always

[ client_and_server_ext ]
keyUsage                = critical,digitalSignature,keyEncipherment
extendedKeyUsage        = clientAuth,serverAuth
basicConstraints        = CA:false
subjectKeyIdentifier    = hash
authorityKeyIdentifier  = keyid:always


[ root_crl_issuer ]
O = $organization
OU = $service
CN = $ca

# CRL extensions exist solely to point to the CA certificate that has issued
# the CRL.
[ crl_ext ]
authorityKeyIdentifier  = keyid:always,issuer:always
EOF
}


case "$1" in
    new-root)
        shift;
        new-root $@
    ;;
    create-new-ca)
        shift;
        create-new-ca $@
    ;;
    create-server-only-cert)
        shift;
        create-server-only-cert $@
    ;;
    create-client-only-cert)
        shift;
        create-client-only-cert $@
    ;;
    create-client-and-server-cert)
        shift;
        create-client-and-server-cert $@
    ;;
    revoke-cert)
        shift;
        revoke-cert $@
    ;;
    update-crl)
        shift;
        update-crl $@
    ;;
    *)
        show-help
    ;;
esac

