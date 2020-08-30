#!/usr/bin/env python3

import configparser
import logging
import os.path
import random
import sys
import time

import ffpyplayer.player as ff
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"  # silence ad
import pygame


SLUG = __package__

log = logging.getLogger(__name__)

_current_background = None
_last_music = None

# Platform-dependent!
CONFIG = os.path.expanduser(os.path.join(os.environ.get('XDG_CONFIG_HOME', '~/.config'),
                                         SLUG, '{0}.ini'.format(SLUG)))
USERDATA = os.path.expanduser(os.path.join(os.environ.get('XDG_DATA_HOME', '~/.local/share'),
                                           SLUG))

class COLORS:
    WHITE   = pygame.colordict.THECOLORS['white']
    MAGENTA = pygame.colordict.THECOLORS['magenta']
    BLACK   = pygame.colordict.THECOLORS['black']

class OPTIONS:
    FULLSCREEN = False
    LOGLEVEL = logging.INFO
    DEBUG = False
    SCREEN_SIZE = (1600, 900)  # Fullscreen ignores this and use desktop resolution
    FPS = 60  # 0 for Unbounded FPS
    BG_COLOR = COLORS.BLACK  # Background color (Magenta)
    CAPTION = "Videokê RES"
    DATADIR = os.path.join(os.path.dirname(__file__), 'data')
    CONFIG = CONFIG
    MUSICDIR = os.path.join(DATADIR, 'music')


def extension(filepath:str) -> str:
    """Return the normalized filename extension: lowercase without leading dot

    Can be empty. Does not consider POSIX hidden files to be extensions.
    Example: extension('A.JPG') -> 'jpg'
    """
    return os.path.splitext(filepath)[1][1:].lower()

def scale_size(original, size=(), proportional=True, multiple=(1, 1)):
    """Enlarge or shrink <original> size so it fits a <size>.

    If <proportional>, rescaled size will maintain the original width and
    height proportions, so resulting size may be smaller than requested in
    either dimension.

    <multiple> rounds down size to be a multiple of given integers. It
    allow themes to ensure cards have integer size, but may slightly change
    image aspect ratio.

    <original>, <size>, <multiple> and the return value are 2-tuple
    (width, height). Returned width and height are rounded to integers.
    """
    def round_to_multiple(size, multiple):
        return (int(size[0] / multiple[0]) * multiple[0],
                int(size[1] / multiple[1]) * multiple[1])

    if not size or size == original:
        return round_to_multiple(original, multiple)

    if not proportional:
        return round_to_multiple(size, multiple)

    rect = pygame.Rect((0,0), original)
    result = rect.fit(pygame.Rect((0,0), size))
    return round_to_multiple((result.width, result.height), multiple)


def resize(image, size=(), proportional=True, colorkey=None):
    """Return a resized (and converted) image surface

    <colorkey> is the color to be rendered transparent. It may be an (R, G, B) 3-tuple
    color or a (X, Y) 2-tuple, in which case the transparent color key is taken from
    the image (X, Y) pixel.

    See scale_size() for documentation on <size> and <proportional>.

    For regular images, requesting a <size> different than the original (after processing
    aspect and roundings) will use pygame.transform.smoothscale().
    """
    if colorkey is None:
        image = image.convert_alpha()
    else:
        # If colorkey
        if len(colorkey) == 2:
            colorkey = image.get_at(colorkey)
        image.set_colorkey(colorkey)
        image = image.convert()

    size = scale_size(image.get_size(), size, proportional)
    if size == image.get_size():
        return image

    # transform.smoothscale() requires a 24 or 32-bit image, so...
    if image.get_bitsize() not in (24, 32):
        image = image.convert_alpha()

    return pygame.transform.smoothscale(image, size)


def load_image(path, size=(), proportional=True):
    """Wrapper for pygame.image.load. See resize() for arguments"""
    return resize(pygame.image.load(path), size, proportional)


def random_music():
    global _last_music

    music = {}
    for mdir in (
            os.path.join(OPTIONS.DATADIR, 'music'),
            os.path.join(USERDATA, 'music'),
            OPTIONS.MUSICDIR,
    ):
        music.update({f: os.path.join(mdir, f)
                      for f in (os.listdir(mdir) if os.path.isdir(mdir) else [])
                      if extension(f) == 'mp4'})
    log.debug("%d music found", len(music))
    if not music:
        raise FileNotFoundError("No music found!")

    if len(music) == 1:
        video = tuple(music.keys())[0]
    else:
        while True:
            video = random.choice(tuple(music.keys()))
            if video != _last_music:
                break
    _last_music = music[video]
    return _last_music


def random_background(surface):
    global _current_background
    bgdir = os.path.join(OPTIONS.DATADIR, 'backgrounds')
    bgs = tuple(os.path.join(bgdir, f)
                for f in os.listdir(bgdir)
                if extension(f) in ('bmp', 'jpg', 'jpeg', 'png'))
    if not bgs:
        return

    if len(bgs) == 1:
        bg = bgs[0]
    else:
        while True:
            bg = random.choice(bgs)
            if bg != _current_background:
                break

    surface.fill(OPTIONS.BG_COLOR)
    centerblit(load_image(bg, surface.get_size()), surface)
    _current_background = bg


def centerblit(surface, dest):
    w, h = dest.get_size()
    x, y = surface.get_size()
    dest.blit(surface, ((w//2)-(x//2), (h//2)-(y//2)))


class VideoPlayer:
    _fmt_map = {
        'rgb24': 'RGB',
        None: 'RGB',
    }

    def __init__(self, path, surface):
        self.player = ff.MediaPlayer(path)
        self.surface = surface
        self.image = None
        self.wait = 0
        self.finished = False

    @property
    def has_finished(self):
        return self.finished

    def play(self):
        """Display a frame image if needed, and return True if so."""

        # No player, no play
        if not self.player:
            return

        # Got any scheduled frame image to display?
        if self.image:
            # Is it too early to display it?
            if time.time() < self.wait:
                return
        else:
            # Get the next frame image
            frame, val = self.player.get_frame()

            # Has video ended?
            if val == 'eof':
                self.stop()
                return

            # Is frame empty?
            if frame is None:
                return

            # Save image
            self.image = frame[0]

            # Do we need to wait / schedule before display?
            if val > 0:
                self.wait = time.time() + val
                return

        # Display it
        try:
            image = pygame.image.frombuffer(
                self.image.to_bytearray()[0],
                self.image.get_size(),
                self._fmt_map.get(self.image.get_pixel_format(), None)
            )
            centerblit(resize(image, self.surface.get_size()), self.surface)
        except Exception as e:
            log.error(e)
            self.stop()
            return

        # Clear schedule and report that image was displayed
        self.image = None
        return True

    def stop(self):
        if self.player:
            self.player.close_player()
            self.player = None
        self.surface = None
        self.image = None
        self.wait = 0
        self.finished = True


def main(argv=None):
    """ Main Program"""
    if argv is None:
        argv = sys.argv[1:]

    # Soon to be replaced by a proper argparse
    for i, arg in enumerate(argv):
        if   arg in ('-f', "--fullscreen"):               OPTIONS.FULLSCREEN = True
        elif arg in ('-q', "--quiet"):                    OPTIONS.LOGLEVEL = logging.WARNING
        elif arg in ('-d', "--debug", '-v', "--verbose"): OPTIONS.LOGLEVEL = logging.DEBUG
        elif arg in ('-F', "--fps", "--FPS"):             OPTIONS.FPS = int(argv[i+1])
        elif arg in ('-c', "--config"):                   OPTIONS.CONFIG = argv[i+1]
    OPTIONS.DEBUG = OPTIONS.LOGLEVEL == logging.DEBUG

    logging.basicConfig(level=OPTIONS.LOGLEVEL, format='%(levelname)s: %(message)s')

    cp = configparser.ConfigParser(inline_comment_prefixes='#')
    if cp.read((OPTIONS.CONFIG,
                CONFIG,
                os.path.join(OPTIONS.DATADIR, '..', '..', os.path.basename(CONFIG))
               ), encoding='utf-8'):
        try:
            OPTIONS.MUSICDIR = os.path.expanduser(cp.get(SLUG, 'music'))
        except configparser.NoOptionError as e:
            log.warning("%s in %s", e, OPTIONS.CONFIG)
    for i, arg in enumerate(argv):
        if arg in ('-m', "--music", "--music-dir"):
            OPTIONS.MUSICDIR = argv[i+1]
    log.info('Reading music from: %s', OPTIONS.MUSICDIR)

    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pygame.display.init()

    # Set caption and icon
    pygame.display.set_caption(OPTIONS.CAPTION)
    pygame.display.set_icon(pygame.image.load("{0}.png".format(SLUG)))

    # Set the screen
    flags = 0
    size = OPTIONS.SCREEN_SIZE
    if OPTIONS.FULLSCREEN:
        flags |= pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
        size = (0, 0)  # current desktop resolution
    screen = pygame.display.set_mode(size, flags)

    # Set the background
    random_background(screen)

    clock = pygame.time.Clock()
    done = False
    dirty = True
    player = None
    while not done:
        for event in pygame.event.get():
            if   ((event.type in (pygame.QUIT,)) or
                  (event.type == pygame.MOUSEBUTTONUP and event.button == pygame.BUTTON_RIGHT) or
                  (event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE)):
                done = True

            elif ((event.type == pygame.MOUSEBUTTONUP and event.button == pygame.BUTTON_LEFT) or
                  (event.type == pygame.KEYUP and event.key == pygame.K_SPACE)):
                random_background(screen)
                dirty = True

            elif ((event.type == pygame.KEYUP and event.key == pygame.K_RETURN)):
                if player:
                    player.stop()
                else:
                    try:
                        video = random_music()
                        player = VideoPlayer(video, screen)
                        log.info("Playing: %s", video)
                    except FileNotFoundError as e:
                        log.error(e)

        if player:
            if player.finished:
                player = None
                random_background(screen)
                dirty = True
            else:
                dirty = player.play()

        if dirty:
            pygame.display.update()
            dirty = False
        clock.tick(OPTIONS.FPS)

    pygame.quit()


def start():
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("Aborting")
        sys.exit(1)
