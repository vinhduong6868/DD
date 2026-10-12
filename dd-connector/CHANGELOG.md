# 2.0.1

- Persist private Connector state in Supervisor's app-specific config volume.
- Preserve existing Local, Cloud and sharing state when migrating from the local app to the repository app.
- Do not copy Supervisor tokens, Home Assistant tokens or options into the migration directory.

# 2.0.0

- Local pairing credentials are isolated per pinned Core certificate.
- Existing beta Local pairing migrates once before accepting configuration changes.
- Cloud and Local continue to use their existing transport and Core authority.
- Sharing selections persist through updates and restarts.
- Repository installation supports Home Assistant Supervisor update discovery and Auto update.
- The Connector does not receive Supervisor management privileges or implement a self-updater.
- When changing to a different Core certificate, pair with that Core once. A certificate rotation also requires pairing again.
