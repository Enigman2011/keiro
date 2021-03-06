import pygame
import sys

from particle import World as PhysicsWorld


class View(object):
    def __init__(self, obstacles, pedestrians, world_size):
        self.obstacles = obstacles
        self.pedestrians = pedestrians
        maxx, maxy = world_size
        self.world_bounds = (0, maxx, 0, maxy)


class DummyCanvas(object):
    # abstract canvas class, can be used as dummy for not drawing
    def fill(self, color):
        pass

    def _color(self, input_color):
        pass

    def line(self, from_coordinate, to_coordate,
             color="black", stroke_width=2):
        pass

    def polygon(self, coordinates, color):
        for c0, c1 in zip(coordinates, coordinates[1:] + [coordinates[0]]):
            self.line(c0, c1, color)

    def circle(self, center, radius, color="black", stroke_width=2):
        pass

    def blit(self, canvas, position):
        pass

    def flush(self):
        pass

    def image_string(self):
        pass

    def rect(self, top, left, bottom, right, color="black", stroke_width=0):
        pass


class PygameCanvas(DummyCanvas):
    def __init__(self, surface):
        self.surface = surface

    def fill(self, color):
        self.surface.fill(color)

    def _color(self, input_color):
        if isinstance(input_color, basestring):
            return pygame.Color(input_color)
        assert isinstance(input_color, tuple)
        return input_color

    def line(self, from_coordinate, to_coordate,
             color="black", stroke_width=1):
        pygame.draw.line(
            self.surface,
            self._color(color),
            map(int, from_coordinate),
            map(int, to_coordate),
            stroke_width
        )

    def circle(self, center, radius,
               color="black", stroke_width=2):
        pygame.draw.circle(
            self.surface,
            self._color(color),
            map(int, center),
            int(radius),
            stroke_width
        )

    def blit(self, source_canvas, position):
        if isinstance(source_canvas, PygameCanvas):
            self.surface.blit(source_canvas.surface, position)

    def flush(self):
        pygame.display.flip()

    def get_image_string(self):
        return pygame.image.tostring(self.surface, "RGB")

    def rect(self, top, left, bottom, right, color="black", stroke_width=0):
        color = self._color(color)
        pygame_rect = pygame.Rect(left, top, right-left, bottom-top)
        pygame.draw.rect(self.surface, color, pygame_rect, stroke_width)


class World(PhysicsWorld):
    def __init__(self, size):
        super(World, self).__init__()
        self.size = size
        self.units = []
        self.obstacles = []

        self.clock = pygame.time.Clock()
        self.timestep = 0  # default: real time
        self.show_fps = False
        self.encoders = []

        self.collision_list = []
        self.avg_groundspeed_list = []

    def init(self):
        pygame.init()
        pygame.display.set_caption("Crowd Navigation")
        self.display_canvas = PygameCanvas(
            pygame.display.set_mode(self.size)
        )
        self.debugcanvas = PygameCanvas(
            pygame.Surface(
                self.size,
                masks=pygame.SRCALPHA
            ).convert_alpha()
        )
        self._time = 0
        self._iterations = 0
        self.update(0)  # so we have no initial collisions
        for u in self.units:
            u.init(
                View(
                    self.get_obstacles(),
                    [],
                    self.size
                )
            )

    def set_timestep(self, timestep):
        self.timestep = timestep

    def set_show_fps(self, show=True):
        self.show_fps = show

    def add_unit(self, unit):
        self.units.append(unit)
        self.bind(unit)

    def remove_unit(self, unit):
        self.units.remove(unit)
        self.unbind(unit)

    def add_obstacle(self, obstacle):
        self.obstacles.append(obstacle)
        for line in obstacle.bounds:
            self.bind(line)

    def remove_obstacle(self, obstacle):
        for line in obstacle.bounds:
            self.unbind(line)
        self.obstacles.remove(obstacle)

    def add_encoder(self, encoder):
        self.encoders.append(encoder)

    def get_time(self):
        return self._time

    def advance(self):
        if self.timestep == 0:
            dt = self.clock.tick() / 1000.0  # use real time
        else:
            self.clock.tick()
            dt = self.timestep

        self._time += dt
        self._iterations += 1

        self.update(dt)

        self.debugcanvas.fill((255, 255, 255, 0))  # transparent

        for u in self.units:
            if u.view_range != 0:
                view = View(self.get_obstacles(),
                            self.particles_in_range(u, u.view_range),
                            self.size)
                # Marc's occlusion code
                # view = View(
                #     self.get_obstacles(),
                #     # with occlusion
                #     self.particles_in_view_range(u, u.view_range),
                #     self.size
                # )
            else:
                view = View(self.get_obstacles(), [], self.size)

            u._think(dt, view, self.debugcanvas)

        if self.show_fps:
            sys.stdout.write("%f fps           \r" % self.clock.get_fps())
            sys.stdout.flush()

        self.render(self.display_canvas)
        return dt

    def render(self, canvas):
        canvas.fill((255, 255, 255))

        for o in self.obstacles:
            o.render(canvas)
        ID = 0

        canvas.blit(self.debugcanvas, (0, 0))

        for u in self.units:
            #u.render_ID(screen, ID)
            u.render(canvas)
            ID = ID + 1

        canvas.flush()

        if len(self.encoders) > 0:
            imagestring = canvas.get_image_string()
            for enc in self.encoders:
                enc.add_frame(imagestring)
