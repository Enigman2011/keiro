import pygame
import math
import random
from agent import Agent, iteration
from fast.physics import Vec2d, linesegdist2, line_distance2, angle_diff
from stategenerator import PrependedGenerator, ExtendingGenerator, StateGenerator

class Arty(Agent):
	SAFETY_THRESHOLD = 0.9 #this has practically no effect in the current implementation
	GLOBALMAXEDGE = 70
	LOCALMAXEDGE = 50
	LOCALMAXSIZE = 10
	FREEMARGIN = 2
	
	class Node:
		def __init__(self, position, angle, parent, time = None, freeprob = None):
			self.position = position
			self.angle = angle
			self.time = time
			self.parent = parent
			self.freeprob = freeprob
			
	def __init__(self, parameter):
		if parameter is None:
			parameter = 60
		super(Arty, self).__init__(parameter)
		self.GLOBALNODES = parameter
	
	def globaltree(self, view):
		#RRT from goal
		nodes = [self.Node(self.goal, None, None)]
		sg = StateGenerator(0, 640, 0, 480) #TODO: remove hardcoded world size

		for newpos in sg.generate_n(self.GLOBALNODES):
			besttime = None
			bestnode = None
			for tonode in nodes:
				topos = tonode.position
				connectable = True
				for o in view.obstacles:
					if line_distance2(topos, newpos, o.p1, o.p2) < (self.radius + self.FREEMARGIN)**2:
						connectable = False
						break
						
				if connectable:
					dist = topos.distance_to(newpos)
					if tonode.parent is None:
						turndist = 0 #goal node
					else:
						turndist = abs(angle_diff((topos - newpos).angle(), tonode.angle))
					time = dist/self.speed + turndist/self.turningspeed
					
					if bestnode is None or time < besttime:
						besttime = time
						bestnode = tonode
						
			if bestnode:
				topos = bestnode.position
				diff = newpos - topos
				angle = diff.angle()
				vdir = diff.norm()
				difflen = diff.length()
				div = int(math.ceil(difflen/self.GLOBALMAXEDGE))
				prev = bestnode
				#subdivide the new edge
				for d in xrange(1, div+1):
					newnode = self.Node(topos + diff*d/div, angle, prev)
					nodes.append(newnode)
					prev = newnode
		
		self.globalnodes = nodes
		print "Done building global roadmap tree", len(self.globalnodes)
		
	def init(self, view):
		"""Builds the static obstacle map, global roadmap"""
		self.globaltree(view)
	
	def future_position(self, pedestrian, time):
		return pedestrian.position + pedestrian.velocity*time
		
	def freeprob_pedestrians(self, position, view, time):
		"""Returns probability that specified position will be collision free at specified time with respect to pedestrians"""		
		for p in view.pedestrians:
 			pedestrianpos = self.future_position(p, time) #extrapolated position
			if position.distance_to(pedestrianpos) < (self.radius + p.radius + self.FREEMARGIN):
				return 0 #collision with pedestrian
		return 1
	
	def freeprob_turn(self, position, a1, a2, view, starttime):
		dur = angle_diff(a1, a2)/self.turningspeed
		for p in view.pedestrians:
			p1 = p.position
			p2 = self.future_position(p, dur) #extrapolate
			if linesegdist2(p1, p2, position) < (self.radius + p.radius + self.FREEMARGIN)**2:
				return 0	
		return 1
	
	def freeprob_line(self, p1, p2, view, starttime):
		if p1 == p2:
			return self.freeprob_pedestrians(p1, view, starttime)
		
		for o in view.obstacles:
			if line_distance2(o.p1, o.p2, p1, p2) < (self.radius + self.FREEMARGIN)**2:
				return 0
							
		diff = p2 - p1
		length = diff.length()
		v = diff/length
		resolution = self.radius*2
		numsegments = int(math.ceil(length/resolution))
		segmentlen = length/numsegments
		timediff = segmentlen/self.speed
		
		freeprob = 1.0
		for i in xrange(numsegments+1):
			freeprob *= self.freeprob_pedestrians(p1 + v*i*segmentlen, view, starttime + i*timediff)
		
		return freeprob
	
	def freeprob_turn_line(self, p1, a1, p2, view, starttime):
		"""Free probability for turning and then walking on a straight line"""
		a2 = (p2-p1).angle()
		dt = abs(angle_diff(a1, a2))/self.turningspeed
		free = self.freeprob_turn(p1, a1, a2, view, starttime)
		free *= self.freeprob_line(p1, p2, view, starttime + dt)
		return free
		
	def segment_time(self, a1, p1, p2):
		"""Returns time to get from a state (a1, p1) to ((p2-p1).angle(), p2)"""
		diff = p2 - p1
		turningtime = abs(angle_diff(a1, diff.angle()))/self.turningspeed
		movetime = diff.length()/self.speed
		return turningtime + movetime
		
	def getpath(self, view):
		"""Use the Art algorithm to get a path to the goal"""
		#first try to find global node by local planner from current position
		testpath, testtime = self.find_globaltree(self.position, self.angle, view, 0, 1)
		if testpath:
			return testpath
		#print "Cannot find global path from current, extending search tree"
		start = Arty.Node(self.position, self.angle, parent = None, time = 0, freeprob = 1)
		nodes = [start]

		states = ExtendingGenerator((self.position.x - self.view_range, self.position.x + self.view_range,
									self.position.y - self.view_range, self.position.y + self.view_range),
									(0,640,0,480), #TODO: remove hardcoded world size)
									10) #arbitrarily chosen
		
		#always try to use the nodes from the last solution in this iterations so they are kept if still the best
		for i in xrange(self.waypoint_len()):
			pos = self.waypoint(i).position
			#if pos.distance_to(self.position) <= self.radius:
			states.prepend(pos)
		
		bestsolution = None
		bestsolution_time = None
		
		for nextpos in states.generate_n(self.LOCALMAXSIZE):
			bestparent = None
			for n in nodes:
				freeprob = self.freeprob_turn_line(n.position, n.angle, nextpos, view, n.time)
				endtime = n.time + self.segment_time(n.angle, n.position, nextpos)
				
				newprob = freeprob * n.freeprob
				if newprob < self.SAFETY_THRESHOLD:
					continue
				if bestparent is None or besttime > endtime:
					bestparent = n
					besttime = endtime

			if bestparent is not None:
				pygame.draw.line(self.debugsurface, (0,255,0), bestparent.position, nextpos)
				#subdivide the new edge
				diff = nextpos - bestparent.position
				angle = diff.angle()
				difflen = diff.length()
				vdir = diff/difflen
				div = int(math.ceil(difflen/self.LOCALMAXEDGE))
				
				lastnode = bestparent
				
				for d in xrange(1, div+1):
					#not 100% sure everything here is correct, variable names are a bit confusing...
					subpos = bestparent.position + diff*d/div
					freeprob = self.freeprob_turn_line(lastnode.position, lastnode.angle, subpos, view, lastnode.time)
					dt = self.segment_time(lastnode.angle, lastnode.position, subpos)
					newnode = self.Node(subpos, angle, parent = lastnode, time = lastnode.time + dt, freeprob = lastnode.freeprob * freeprob)
					lastnode = newnode
					nodes.append(newnode)

					#get the best path to the global graph on to the goal from the new node
					gpath, gtime = self.find_globaltree(newnode.position, newnode.angle, view, newnode.time, newnode.freeprob)	
					if gpath is not None:
						if bestsolution is None or gtime < bestsolution_time:
							path = []
							n = newnode
							while n != None:
								path.append(n.position)
								n = n.parent
							path.reverse()
						
							for gpos in gpath:
								path.append(gpos)
							
							bestsolution = path
							bestsolution_time = gtime
		return bestsolution
	
	def find_globaltree(self, p1, a1, view, time, startprob):
		"""Tries to reach global tree from position/angle
		
			Returns (path, time) to get to goal"""
			
		bestpath = None
		besttime = None
	
		for n in self.globalnodes:
			a2 = (n.position - p1).angle()
			free = startprob * self.freeprob_turn(p1, a1, a2, view, time)
			time += abs(angle_diff(a1, a2))/self.turningspeed
			free *= self.freeprob_turn_line(p1, a1, n.position, view, time)
			
			if free >= self.SAFETY_THRESHOLD:
				#try to reach goal from global node
				path = []
				cur = n
				while cur.parent != None:
					path.append(cur.position)
					free *= self.freeprob_turn_line(cur.position, cur.angle, cur.parent.position, view, time)
					time += self.segment_time(cur.angle, cur.position, cur.parent.position)
					cur = cur.parent
					
				path.append(cur.position)
				
				if bestpath is None or time < besttime:
					bestpath = path
					besttime = time
					
		return (bestpath, besttime)
			
			
	@iteration	
	def think(self, dt, view, debugsurface):
		if not self.goal:
			return
		self.view = view
		self.debugsurface = debugsurface
		for n in self.globalnodes:
			if n.parent:
				pygame.draw.line(debugsurface, pygame.Color("black"), n.position, n.parent.position)
			pygame.draw.circle(debugsurface, pygame.Color("red"), n.position, 2, 0)

		for p in view.pedestrians:
			pygame.draw.circle(debugsurface, pygame.Color("green"), p.position, p.radius+2, 2)

		path = self.getpath(view)
		self.waypoint_clear()
		
		if path:
			for p in path:
				self.waypoint_push(p)
