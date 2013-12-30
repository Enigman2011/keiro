import time
import pygame
from vector2d import Vec2d
from geometry import linesegdist2
from keiro.unit import Unit


class AgentRegistrar(type):
    register = {}

    def __new__(cls, name, bases, dct):
        assert name not in AgentRegistrar.register, 'Multiple agents %r defined!' % name
        ret = AgentRegistrar.register[name] = type.__new__(
            cls, name, bases, dct)
        return ret


class IterationStats(object):
    """Registers algorithm iteration statistics"""
    def __init__(self):
        self._times = []
        self._start = None

    def start_iteration(self):
        self._start = time.clock()

    def end_iteration(self):
        self._times.append(time.clock() - self._start)
        assert(self._start is not None)
        self._start = None

    def get_max_iterationtime(self):
        return max(self._times)

    def get_min_iterationtime(self):
        return min(self._times)

    def get_avg_iterationtime(self):
        return sum(self._times) / len(self._times)


class Agent(Unit):
    """Base class for all navigational algorithms"""
    __metaclass__ = AgentRegistrar

    view_range = 150

    def __init__(self, parameter):
        super(Agent, self).__init__()
        self.parameter = parameter
        self.color = (100, 100, 255)
        self.travel_length = 0
        self.iterations = IterationStats()

    def __repr__(self):
        return "{0}({1})".format(
            self.__class__.__name__,
            self.parameter
        )

    def render(self, screen):
        #draw a cross over the goal
        screen.line(
            self.goal + Vec2d(-10, -10),
            self.goal + Vec2d(10, 10),
            (255, 0, 0)
        )
        screen.line(
            self.goal + Vec2d(10, -10),
            self.goal + Vec2d(-10, 10),
            (255, 0, 0),
        )

        super(Agent, self).render(screen)
        #pygame.draw.circle(screen, self.color,
        #   map(int, self.position), int(self.radius), 0)

        #draw all waypoints
        last = self.position
        for i in xrange(self.waypoint_len()):
            screen.line(
                last, self.waypoint(i).position, (0, 0, 0)
            )
            last = self.waypoint(i).position
            screen.line(last, last, (0, 0, 0))

        #draw viewrange
        screen.circle(
            self.position,
            self.view_range,
            (100, 100, 100),
            1
        )

    def init(self, view):
        """Called before simulation starts

        Allows for agent initialization using information
        about static obstacles.
        """
        pass

    def _think(self, dt, view, debugsurface):
        if self.goal_occupied(view):
            print "Goal occupied"
        self.iterations.start_iteration()
        self.think(dt, view, debugsurface)
        self.iterations.end_iteration()

    def think(self, dt, view, debugsurface):
        raise NotImplementedError(
            'An Agent needs to have a brain! Implement the `think()` method'
        )

    def goal_occupied(self, view):
        """Returns if goal is occupied by obstacle/unit that isn't moving

        Convenience method that can be used to trigger fallback
        to a nearby goal or similar.
        """
        for line in view.obstacles:
            if linesegdist2(line.p1, line.p2, self.goal) < self.radius ** 2:
                return True

        for p in view.pedestrians:
            if p.velocity.length2() == 0.0:
                if p.position.distance_to2(self.goal) < p.radius:
                    return True

        return False
