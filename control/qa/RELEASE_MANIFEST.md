# QA RELEASE MANIFEST — 20260902-1150

status=NOT_A_FINAL_DEPLOY_PACKAGE  
source_head_under_test=3c892d1a45aaaad34d695e1fbc9f30604cb0a73e  
GLOBAL_RELEASE=NO_GO

## Isolated UI candidate SHA-256

- `frontend/public_html/assets/app.css` `fabf02b698a2852cc9ad695c39e10f0a095e5f2049c65017575f9db39617805c`
- `frontend/public_html/assets/app.js` `a25f0bbd8e0b40cc8d7d3c1e0fd88603ae3efc569d7e6892ead2ba9a80c83567`
- `frontend/public_html/assets/shield.svg` `32ece9c6bc77357abf4f235b79bf58fe53448ee83d7940461ad0689c4e33e9e9`
- `frontend/public_html/index.html` `2b785bd320e004ceffb8e0fe55a6f7b6f11a75795b6d8938858944fed87d87c9`
- `frontend/public_html/manifest.webmanifest` `608acca93eaa1d420d820688933048aa82216f5f36a78482f183d16a56f541c8`
- `frontend/public_html/offline.html` `a760ed58c7daaeb675e4987634e0ec6c6ee2fdab3a49b3846de9081ca61f0636`
- `frontend/public_html/sw.js` `1bc2b44d9c87fe1b0622f60909905dca54337fcec21d8be3542995d684321768`

## Upstream authority hashes

- Core v0.3.13 patch: `ffc2974e6f131ffec2050762ed6b70b6be307bb9554fc150572b53eb37b7f56e`
- Stage03 exact package: `6419367f716fac62735b81e97c5a802318c3dcb3e332f7fcc0659ae25e0f3de9`
- Stage04 prior exact authority package: `5199a8c9f35a53d4e7d12d8cf744a415e64c1456b5a7b2d3b9d88cba6f53d894`
- UI source-manifest declared hash: `22bb36af4d6eed4e5d9cdba1626af8b353e3ed89e20256fdd148a9a900c56ffa`

## Missing release artifacts

FINAL_DEPLOY_PACKAGE_SHA256=ABSENT  
FINAL_UPLOAD_MANIFEST_SHA256=ABSENT  
ROLLBACK_PACKAGE_SHA256=ABSENT  
PRODUCTION_RESTORE_CERTIFICATE=ABSENT  
FINAL_PUBLIC_HTML_RECURSIVE_SECURITY_SCAN=ABSENT

The isolated UI candidate is not a replacement for the final serial package. Preserve/harden production `.htaccess`; exclude DB snapshots, private Evidence, secrets/PII, dev scripts/docs/placeholders and `DEMO-APERTA.flag` until READY.
