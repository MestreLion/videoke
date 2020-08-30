You may copy MP4 music files here

Music files are read from, in priority order:
- Directory from command-line argument '-m|--music', if any
- Directory in '[videoke] music' setting from config files, if any. Config files are:
   - Command-line argument '-c|--config', if any
   - ${XDG_CONFIG_HOME}/videoke/videoke.ini, defaults to ~/.config/videoke/videoke.ini
   - DATADIR/../../videoke.ini, i.e., in repository root
- ${XDG_DATA_HOME}/videoke/music, defaults to ~/.local/share/videoke/music
- DATADIR/music, this directory
