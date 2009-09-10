# This file is part of Merlin.
# Merlin is the Copyright (C)2008-2009 of Robin K. Hansen, Elliot Rosemarine, Andreas Jacobsen.

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
 
import re
from sqlalchemy import or_
from sqlalchemy.sql import desc
from Core.exceptions_ import PNickParseError
from Core.db import session
from Core.maps import Planet, Alliance, Intel
from Core.loadable import loadable
from Core.paconf import PA

@loadable.module("member")
class idler(loadable):
    """Target search, ordered by idle ticks"""
    usage = "  [alliance] [race] [<|>][size] [<|>][value] [bash] (must include at least one search criteria, order doesn't matter)"
    paramre = re.compile(r"\s+(.+)")
    alliancere=re.compile(r"^(\S+)$")
    racere=re.compile(r"^(ter|cat|xan|zik|eit|etd)$",re.I)
    rangere=re.compile(r"^(<|>)?(\d+)$")
    bashre=re.compile(r"^(bash)$",re.I)
    clusterre=re.compile(r"^c(\d+)$",re.I)
    
    def execute(self, message, user, params):
        
        alliance=Alliance()
        race=None
        size_mod=None
        size=None
        value_mod=None
        value=None
        bash=False
        attacker=None
        cluster=None

        params=params.group(1).split()

        for p in params:
            m=self.bashre.search(p)
            if m and not bash:
                bash=True
                if not self.is_user(user):
                    raise PNickParseError
                if user.planet is not None:
                    attacker = user.planet
                else:
                    message.alert("Usage: %s (you must set your planet in preferences to use the bash option (!pref planet=x:y:z))" % (self.usage,))
                    return
                continue
            m=self.clusterre.search(p)
            if m and not cluster:
                cluster=int(m.group(1))
            m=self.racere.search(p)
            if m and not race:
                race=m.group(1)
                continue
            m=self.rangere.search(p)
            if m and not size and int(m.group(2)) < 32768:
                size_mod=m.group(1) or '>'
                size=m.group(2)
                continue
            m=self.rangere.search(p)
            if m and not value:
                value_mod=m.group(1) or '<'
                value=m.group(2)
                continue
            m=self.alliancere.search(p)
            if m and not alliance.name and not self.clusterre.search(p):
                alliance = Alliance(name="Unknown") if m.group(1).lower() == "unknown" else Alliance.load(m.group(1))
                if alliance is None:
                    message.reply("No alliance matching '%s' found" % (m.group(1),))
                    return
                continue

        Q = session.query(Planet, Intel)
        if alliance.id:
            Q = Q.join(Planet.intel)
            Q = Q.filter(Intel.alliance == alliance)
        else:
            Q = Q.outerjoin(Planet.intel)
            if alliance.name:
                Q = Q.filter(Intel.alliance == None)
        Q = Q.filter(Planet.active == True)
        if race:
            Q = Q.filter(Planet.race.ilike(race))
        if size:
            Q = Q.filter(Planet.size.op(size_mod)(size))
        if value:
            Q = Q.filter(Planet.value.op(value_mod)(value))
        if bash:
            Q = Q.filter(or_(Planet.value.op(">")(attacker.value*PA.getfloat("bash","value")),
                             Planet.score.op(">")(attacker.score*PA.getfloat("bash","score"))))
        if cluster:
            Q = Q.filter(Planet.x == cluster)
        Q = Q.order_by(desc(Planet.idle))
        Q = Q.order_by(desc(Planet.value))
        result = Q[:6]
        
        if len(result) < 1:
            reply="No"
            if race:
                reply+=" %s"%(race,)
            reply+=" planets"
            if alliance:
                reply+=" in intel matching Alliance: %s"%(alliance.name,)
            else:
                reply+=" matching"
            if size:
                reply+=" Size %s %s" % (size_mod,size)
            if value:
                reply+=" Value %s %s" % (value_mod,value)
            message.reply(reply)
            return
        
        replies = []
        for planet, intel in result[:5]:
            reply="%s:%s:%s (%s)" % (planet.x,planet.y,planet.z,planet.race)
            reply+=" Value: %s Size: %s Idle: %s" % (planet.value,planet.size, planet.idle)
            if intel:
                if intel.nick:
                    reply+=" Nick: %s" % (intel.nick,)
                if not alliance.name and intel.alliance:
                    reply+=" Alliance: %s" % (intel.alliance.name,)
            replies.append(reply)
        if len(result) > 5:
            replies[-1]+=" (Too many results to list, please refine your search)"
        message.reply("\n".join(replies))