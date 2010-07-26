# This file is part of Merlin/Arthur.
# Merlin/Arthur is the Copyright (C)2009,2010 of Elliot Rosemarine.

# Individual portions may be copyright by individual contributors, and
# are included in this collective work with permission of the copyright
# owners.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
 
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from sqlalchemy.sql import asc
from Core.db import session
from Core.maps import Planet, Scan
from Arthur.context import render
from Arthur.loadable import loadable, load

@load
class scans(loadable):
    access = "half"
    
    def execute(self, request, user):
        return HttpResponseRedirect("/")

@load
class group(loadable):
    access = "half"
    
    def execute(self, request, user, id):
        Q = session.query(Planet, Scan)
        Q = Q.join(Scan.planet)
        Q = Q.filter(Scan.group_id.ilike("%"+id+"%"))
        Q = Q.order_by(asc(Planet.x), asc(Planet.y), asc(Planet.z), asc(Scan.scantype), asc(Scan.tick))
        result = Q.all()
        if len(result) == 0:
            return HttpResponseRedirect(reverse("scans"))
        
        group = []
        scans = []
        for planet, scan in result:
            if len(group) < 1 or group[-1][0] is not planet:
                group.append((planet, [scan],))
            else:
                group[-1][1].append(scan)
            scans.append(scan)
        
        return render("scans/group.tpl", request, group=group, scans=scans, intel=user.is_member())

@load
class tick(loadable):
    access = "half"
    
    def execute(self, request, user, tick):
        Q = session.query(Planet, Scan)
        Q = Q.join(Scan.planet)
        Q = Q.filter(Scan.tick == tick)
        Q = Q.order_by(asc(Planet.x), asc(Planet.y), asc(Planet.z), asc(Scan.scantype), asc(Scan.tick))
        result = Q.all()
        
        group = []
        for planet, scan in result:
            if len(group) < 1 or group[-1][0] is not planet:
                group.append((planet, [scan],))
            else:
                group[-1][1].append(scan)
        
        return render("scans/tick.tpl", request, tick=tick, group=group)