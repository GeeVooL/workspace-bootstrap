# Host overrides

Add `localhost.yml` here for settings specific to the local workstation, such as
`configure_ghostty: false` or `applications_excluded_categories: [development]`.
Keep private machine configuration outside version control and load it with
`-e @/path/to/settings.yml`. Never commit credentials or machine history.
