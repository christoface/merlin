# This file is part of Merlin.
# Merlin is the Copyright (C)2008,2009,2010 of Robin K. Hansen, Elliot Rosemarine, Andreas Jacobsen.

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
 
import datetime, re, sys, time, traceback, urllib2, shutil, os, errno
from sqlalchemy.sql import text, bindparam
from Core.config import Config
from Core.paconf import PA
from Core.string import decode, excaliburlog
from Core.db import true, false, session
from Core.maps import Updates, galpenis, apenis, Scan
from Core.maps import galaxy_temp, planet_temp, alliance_temp, planet_new_id_search, planet_old_id_search
from Hooks.scans.parser import parse
from ConfigParser import ConfigParser as CP

# ########################################################################### #
# ##############################     CONFIG     ############################# #
# ########################################################################### #

# Config files (absolute or relative paths) for all bots to be updated by this excalibur
configs = ['merlin.cfg']
savedumps = False
useragent = "Merlin (Python-urllib/%s); Alliance/%s; BotNick/%s; Admin/%s" % (urllib2.__version__, Config.get("Alliance", "name"), 
                                                                              Config.get("Connection", "nick"), Config.items("Admins")[0][0])

# ########################################################################### #
# ########################################################################### #

# From http://www.diveintopython.net/http_web_services/etags.html
class DefaultErrorHandler(urllib2.HTTPDefaultErrorHandler):
    def http_error_default(self, req, fp, code, msg, headers):
        result = urllib2.HTTPError(req.get_full_url(), code, msg, headers, fp)
        result.status = code
        return result 


def get_dumps(last_tick, alt=False, useragent=None):
    if alt:
       purl = Config.get("URL", "alt_plan") % (last_tick+1)
       gurl = Config.get("URL", "alt_gal") % (last_tick+1)
       aurl = Config.get("URL", "alt_ally") % (last_tick+1)
    else:
       purl = Config.get("URL", "planets")
       gurl = Config.get("URL", "galaxies")
       aurl = Config.get("URL", "alliances")

    # Build the request for planet data
    req = urllib2.Request(purl)
    if last_tick > 0:
        u = Updates.load()
        req.add_header('If-None-Match', u.etag)
        req.add_header('If-Modified-Since', u.modified)
    if useragent:
        req.add_header('User-Agent', useragent)
    opener = urllib2.build_opener(DefaultErrorHandler())
    planets = opener.open(req)
    try:
        if planets.status == 304:
            excaliburlog("Dump files not modified. Waiting...")
            time.sleep(60)
            return (False, False, False)
        else:
            excaliburlog("Error: %s" % planets.status)
            time.sleep(120)
            return (False, False, False)
    except AttributeError:
        pass

    # Open the dump files
    try:
        req = urllib2.Request(gurl)
        req.add_header('User-Agent', useragent)
        galaxies = opener.open(req)
        req = urllib2.Request(aurl)
        req.add_header('User-Agent', useragent)
        alliances = opener.open(req)
    except Exception, e:
        excaliburlog("Failed gathering dump files.\n%s" % (str(e),))
        time.sleep(300)
        return (False, False, False)
    else:
        return (planets, galaxies, alliances)


def checktick(planets, galaxies, alliances):
    # Skip first three lines of the dump, tick info is on fourth line
    planets.readline();planets.readline();planets.readline();
    # Parse the fourth line and check we have a number
    tick=planets.readline()
    m=re.search(r"tick:\s+(\d+)",tick,re.I)
    if not m:
        excaliburlog("Invalid tick: '%s'" % (tick,))
        time.sleep(120)
        return False
    planet_tick=int(m.group(1))
    excaliburlog("Planet dump for tick %s" % (planet_tick,))
    # Skip next three lines; two are junk, next is blank, data starts next
    planets.readline();planets.readline();planets.readline();

    # As above
    galaxies.readline();galaxies.readline();galaxies.readline();
    tick=galaxies.readline()
    m=re.search(r"tick:\s+(\d+)",tick,re.I)
    if not m:
        excaliburlog("Invalid tick: '%s'" % (tick,))
        time.sleep(120)
        return False
    galaxy_tick=int(m.group(1))
    excaliburlog("Galaxy dump for tick %s" % (galaxy_tick,))
    galaxies.readline();galaxies.readline();galaxies.readline();

    # As above
    alliances.readline();alliances.readline();alliances.readline();
    tick=alliances.readline()
    m=re.search(r"tick:\s+(\d+)",tick,re.I)
    if not m:
        excaliburlog("Invalid tick: '%s'" % (tick,))
        time.sleep(120)
        return False
    alliance_tick=int(m.group(1))
    excaliburlog("Alliance dump for tick %s" % (alliance_tick,))
    alliances.readline();alliances.readline();alliances.readline();

    # Check the ticks of the dumps are all the same and that it's
    #  greater than the previous tick, i.e. a new tick
    if not (planet_tick == galaxy_tick  == alliance_tick):
        excaliburlog("Varying ticks found, sleeping\nPlanet: %s, Galaxy: %s, Alliance: %s" % (planet_tick,galaxy_tick,alliance_tick))
        time.sleep(30)
        return False
    return planet_tick


def penis():
    global bots, prefixes
    # Measure some dicks
    t_start=time.time()
    last_tick = Updates.current_tick()
    history_tick = bindparam("tick",max(last_tick-72, 1))
    t1=time.time()
    session.execute(galpenis.__table__.delete())
    session.execute(text("SELECT setval('galpenis_rank_seq', 1, :false);", bindparams=[false]))
    session.execute(text("INSERT INTO galpenis (galaxy_id, penis) SELECT galaxy.id, galaxy.score - galaxy_history.score FROM galaxy, galaxy_history WHERE galaxy.active = :true AND galaxy.x != 200 AND galaxy.id = galaxy_history.id AND galaxy_history.tick = :tick ORDER BY galaxy.score - galaxy_history.score DESC;", bindparams=[history_tick, true]))
    t2=time.time()-t1
    excaliburlog("galpenis in %.3f seconds" % (t2,))
    t1=time.time()
    session.execute(apenis.__table__.delete())
    session.execute(text("SELECT setval('apenis_rank_seq', 1, :false);", bindparams=[false]))
    session.execute(text("INSERT INTO apenis (alliance_id, penis) SELECT alliance.id, alliance.score - alliance_history.score FROM alliance, alliance_history WHERE alliance.active = :true AND alliance.id = alliance_history.id AND alliance_history.tick = :tick ORDER BY alliance.score - alliance_history.score DESC;", bindparams=[history_tick, true,]))
    t2=time.time()-t1
    excaliburlog("apenis in %.3f seconds" % (t2,))
    t1=time.time()
    for i in range(len(bots)):
        t2=time.time()
        session.execute("DELETE FROM %sepenis;" % (prefixes[i]))
        session.execute(text("SELECT setval('%sepenis_rank_seq', 1, :false);" % (prefixes[i]), bindparams=[false]))
        if bots[i].getboolean("Misc", "acl"):
            session.execute(text("INSERT INTO %sepenis (user_id, penis) SELECT %susers.id, planet.score - planet_history.score FROM %susers, planet, planet_history WHERE %susers.active = :true AND %susers.group_id != 2 AND planet.active = :true AND %susers.planet_id = planet.id AND planet.id = planet_history.id AND planet_history.tick = :tick ORDER BY planet.score - planet_history.score DESC;" % (prefixes[i], prefixes[i], prefixes[i], prefixes[i], prefixes[i], prefixes[i]), bindparams=[history_tick, true]))
        else:
            session.execute(text("INSERT INTO %sepenis (user_id, penis) SELECT %susers.id, planet.score - planet_history.score FROM %susers, planet, planet_history WHERE %susers.active = :true AND %susers.access >= :member AND planet.active = :true AND %susers.planet_id = planet.id AND planet.id = planet_history.id AND planet_history.tick = :tick ORDER BY planet.score - planet_history.score DESC;" % (prefixes[i], prefixes[i], prefixes[i], prefixes[i], prefixes[i], prefixes[i]), bindparams=[bindparam("member",bots[i].getint("Access","member")), history_tick, true]))
        t3=time.time()-t2
        excaliburlog("epenis for %s in %.3f seconds" % (prefixes[i],t3,))
    t2=time.time()-t1
    excaliburlog("epenis in %.3f seconds" % (t2,))
    session.commit()
    t1=time.time()-t_start
    excaliburlog("Total penis time: %.3f seconds" % (t1,))
    session.close()

def closereqs(planet_tick):
    # Close old scan requests
    t_start = time.time()
    for i in range(len(bots)):
        if bots[i].getboolean("Misc", "acl"):
            session.execute(text("UPDATE %srequest SET active=:false WHERE active=:true AND tick < %s;" % (prefixes[i], planet_tick-bots[i].getint("Scans", "reqexpire")), bindparams=[false, true]))
        else:
            session.execute(text("UPDATE %srequest SET active=:false WHERE active=:true AND tick < %s;" % (prefixes[i], planet_tick-bots[i].getint("Misc", "reqexpire")), bindparams=[false, true]))
    session.commit()
    excaliburlog("Expired requests removed in %.3f seconds" % (time.time() - t_start))
    session.close()


def parsescans():
    Q = session.query(Scan).filter(Scan.planet_id == None)
    if Q.count() > 0:
        for s in Q.all():
            parse(s.scanner_id, "scan", s.pa_id).start()

def clean_cache():
    # Clean tick dependant graph cache
    try:
        t_start=time.time()
        if Config.get("Misc", "graphing") != "cached":
            raise OSError
        shutil.rmtree("Arthur/graphs/values/")
        shutil.rmtree("Arthur/graphs/ranks/")
    except OSError:
        pass
    finally:
        t1=time.time()-t_start
        excaliburlog("Clean tick dependant graph cache in %.3f seconds" % (t1,))


def ticker(alt=False):
    global savedumps
    global useragent

    t_start=time.time()
    t1=t_start

    while True:
        try:
            # Get the previous tick number!
            last_tick = Updates.current_tick()
            midnight = Updates.midnight_tick() == last_tick
            hour = bindparam("hour",datetime.datetime.utcnow().hour)
            timestamp = bindparam("timestamp",datetime.datetime.utcnow() - datetime.timedelta(minutes=1))
    
            # How long has passed since starting?
            # If 55 mins, we're not likely getting dumps this tick, so quit
            if (time.time() - t_start) >= (55 * 60):
                excaliburlog("55 minutes without a successful dump, giving up!")
                session.close()
                sys.exit()
    
            (planets, galaxies, alliances) = get_dumps(last_tick, alt, useragent)
            if not planets:
                continue

            # Get header information now, as the headers will be lost if we save dumps
            etag = planets.headers.get("ETag")
            modified = planets.headers.get("Last-Modified")
    
            if savedumps:
                try:
                    os.makedirs("dumps/%s" % (last_tick+1,))
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise
                # Open dump files
                pf = open("dumps/%s/planet_listing.txt" % (last_tick+1,), "w+")
                gf = open("dumps/%s/galaxy_listing.txt" % (last_tick+1,), "w+")
                af = open("dumps/%s/alliance_listing.txt" % (last_tick+1,), "w+")
                # Copy dump contents
                shutil.copyfileobj(planets, pf)
                shutil.copyfileobj(galaxies, gf)
                shutil.copyfileobj(alliances, af)
                # Return to the start of the file
                pf.seek(0)
                gf.seek(0)
                af.seek(0)
                # Swap pointers
                planets = pf
                galaxies = gf
                alliances = af
    
            planet_tick = checktick(planets, galaxies, alliances)
            if not planet_tick:
                continue
    
            if not planet_tick > last_tick:
                excaliburlog("Stale ticks found, sleeping")
                time.sleep(60)
                continue
    
            t2=time.time()-t1
            excaliburlog("Loaded dumps from webserver in %.3f seconds" % (t2,))
            t1=time.time()
    
            if planet_tick > last_tick + 1:
                if alt:
                    excaliburlog("Something is very, very wrong...")
                else:
                    ticker(True)
                continue
    
    ##      # Uncomment this line to allow ticking on the same data for debug
    ##      # planet_tick = last_tick + 1
    
            tick = bindparam("tick",planet_tick)
    
            # Insert a record of the tick and a timestamp generated by SQLA
            session.execute(Updates.__table__.insert().values(id=planet_tick, etag=etag, modified=modified))
    
            # Empty out the temp tables
            session.execute(galaxy_temp.delete())
            session.execute(planet_temp.delete())
            session.execute(alliance_temp.delete())
    
            # If the new tick is below the shuffle tick, empty out all the data
            #  and don't store anything from the dumps other than the tick itself
            if planet_tick <= PA.getint("numbers", "shuffle"):
                excaliburlog("Pre-shuffle dumps detected, emptying out the data")
                planets = None
                galaxies = None
                alliances = None
    
            # Insert the data to the temporary tables
            # Planets
            session.execute(planet_temp.insert(), [{
                                                    "x": int(p[0]),
                                                    "y": int(p[1]),
                                                    "z": int(p[2]),
                                                    "planetname": p[3].strip("\""),
                                                    "rulername": p[4].strip("\""),
                                                    "race": p[5],
                                                    "size": int(p[6] or 0),
                                                    "score": int(p[7] or 0),
                                                    "value": int(p[8] or 0),
                                                    "xp": int(p[9] or 0),
                                                   } for p in [decode(line).strip().split("\t") for line in planets]]) if planets else None
            # Galaxies
            session.execute(galaxy_temp.insert(), [{
                                                    "x": int(g[0]),
                                                    "y": int(g[1]),
                                                    "name": g[2].strip("\""),
                                                    "size": int(g[3] or 0),
                                                    "score": int(g[4] or 0),
                                                    "value": int(g[5] or 0),
                                                    "xp": int(g[6] or 0),
                                                   } for g in [decode(line).strip().split("\t") for line in galaxies]]) if galaxies else None
            # Alliances
            session.execute(alliance_temp.insert(), [{
                                                    "score_rank": int(a[0]),
                                                    "name": a[1].strip("\""),
                                                    "size": int(a[2] or 0),
                                                    "members": int(a[3] or 1),
                                                    "score": int(a[4] or 0),
                                                    "points": int(a[5] or 0),
                                                    "score_total": int(a[6] or 0),
                                                    "value_total": int(a[7] or 0),
                                                    "size_avg": int(a[2] or 0) / int(a[3] or 1),
                                                    "score_avg": int(a[4] or 0) / min(int(a[3] or 1), PA.getint("numbers", "tag_count")),
                                                    "points_avg": int(a[5] or 0) / int(a[3] or 1),
                                                   } for a in [decode(line).strip().split("\t") for line in alliances]]) if alliances else None
    
            t2=time.time()-t1
            excaliburlog("Inserted dumps in %.3f seconds" % (t2,))
            t1=time.time()
    
    # ########################################################################### #
    # ##############################    CLUSTERS    ############################# #
    # ########################################################################### #
    
            # Make sure all the galaxies are active,
            #  some might have been deactivated previously
            session.execute(text("UPDATE cluster SET active = :true;", bindparams=[true]))
    
            # Any galaxies in the temp table without an id are new
            # Insert them to the current table and the id(serial/auto_increment)
            #  will be generated, and we can then copy it back to the temp table
            session.execute(text("INSERT INTO cluster (x, active) SELECT g.x, :true FROM galaxy_temp as g WHERE g.x NOT IN (SELECT x FROM cluster) GROUP BY g.x;", bindparams=[true]))
    
            # For galaxies that are no longer present in the new dump
            session.execute(text("UPDATE cluster SET active = :false WHERE x NOT IN (SELECT x FROM galaxy_temp);", bindparams=[false]))
    
            t2=time.time()-t1
            excaliburlog("Deactivate old clusters and generate new cluster ids in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Update everything from the temp table and generate ranks
            # Deactivated items are untouched but NULLed earlier
            session.execute(text("""UPDATE cluster AS c SET
                                      age = COALESCE(c.age, 0) + 1,
                                      size = t.size, score = t.score, value = t.value, xp = t.xp,
                                      ratio = CASE WHEN (t.value != 0) THEN 10000.0 * t.size / t.value ELSE 0 END,
                                      members = t.count,
                                 """ + (
                                 """
                                      size_growth = t.size - COALESCE(c.size - c.size_growth, 0),
                                      score_growth = t.score - COALESCE(c.score - c.score_growth, 0),
                                      value_growth = t.value - COALESCE(c.value - c.value_growth, 0),
                                      xp_growth = t.xp - COALESCE(c.xp - c.xp_growth, 0),
                                      member_growth = t.count - COALESCE(c.members - c.member_growth, 0),
                                      size_growth_pc = CASE WHEN (c.size - c.size_growth != 0) THEN COALESCE((t.size - (c.size - c.size_growth)) * 100.0 / (c.size - c.size_growth), 0) ELSE 0 END,
                                      score_growth_pc = CASE WHEN (c.score - c.score_growth != 0) THEN COALESCE((t.score - (c.score - c.score_growth)) * 100.0 / (c.score - c.score_growth), 0) ELSE 0 END,
                                      value_growth_pc = CASE WHEN (c.value - c.value_growth != 0) THEN COALESCE((t.value - (c.value - c.value_growth)) * 100.0 / (c.value - c.value_growth), 0) ELSE 0 END,
                                      xp_growth_pc = CASE WHEN (c.xp - c.xp_growth != 0) THEN COALESCE((t.xp - (c.xp - c.xp_growth)) * 100.0 / (c.xp - c.xp_growth), 0) ELSE 0 END,
                                      size_rank_change = t.size_rank - COALESCE(c.size_rank - c.size_rank_change, 0),
                                      score_rank_change = t.score_rank - COALESCE(c.score_rank - c.score_rank_change, 0),
                                      value_rank_change = t.value_rank - COALESCE(c.value_rank - c.value_rank_change, 0),
                                      xp_rank_change = t.xp_rank - COALESCE(c.xp_rank - c.xp_rank_change, 0),
                                      totalroundroids_rank_change = t.totalroundroids_rank - COALESCE(c.totalroundroids_rank - c.totalroundroids_rank_change, 0),
                                      totallostroids_rank_change = t.totallostroids_rank - COALESCE(c.totallostroids_rank - c.totallostroids_rank_change, 0),
                                      totalroundroids_growth = t.totalroundroids - COALESCE(c.totalroundroids - c.totalroundroids_growth, 0),
                                      totalroundroids_growth_pc = CASE WHEN (c.totalroundroids - c.totalroundroids_growth != 0) THEN COALESCE((t.totalroundroids - (c.totalroundroids - c.totalroundroids_growth)) * 100.0 / (c.totalroundroids - c.totalroundroids_growth), 0) ELSE 0 END,
                                      totallostroids_growth = t.totallostroids - COALESCE(c.totallostroids - c.totallostroids_growth, 0),
                                      totallostroids_growth_pc = CASE WHEN (c.totallostroids - c.totallostroids_growth != 0) THEN COALESCE((t.totallostroids - (c.totallostroids - c.totallostroids_growth)) * 100.0 / (c.totallostroids - c.totallostroids_growth), 0) ELSE 0 END,
                                 """ if not midnight
                                     else
                                 """
                                      size_growth = t.size - COALESCE(c.size, 0),
                                      score_growth = t.score - COALESCE(c.score, 0),
                                      value_growth = t.value - COALESCE(c.value, 0),
                                      xp_growth = t.xp - COALESCE(c.xp, 0),
                                      member_growth = t.count - COALESCE(c.members, 0),
                                      size_growth_pc = CASE WHEN (c.size != 0) THEN COALESCE((t.size - c.size) * 100.0 / c.size, 0) ELSE 0 END,
                                      score_growth_pc = CASE WHEN (c.score != 0) THEN COALESCE((t.score - c.score) * 100.0 / c.score * 100, 0) ELSE 0 END,
                                      value_growth_pc = CASE WHEN (c.value != 0) THEN COALESCE((t.value - c.value) * 100.0 / c.value, 0) ELSE 0 END,
                                      xp_growth_pc = CASE WHEN (c.xp != 0) THEN COALESCE((t.xp - c.xp) * 100.0 / c.xp, 0) ELSE 0 END,
                                      size_rank_change = t.size_rank - COALESCE(c.size_rank, 0),
                                      score_rank_change = t.score_rank - COALESCE(c.score_rank, 0),
                                      value_rank_change = t.value_rank - COALESCE(c.value_rank, 0),
                                      xp_rank_change = t.xp_rank - COALESCE(c.xp_rank, 0),
                                      totalroundroids_rank_change = t.totalroundroids_rank - COALESCE(c.totalroundroids_rank, 0),
                                      totallostroids_rank_change = t.totallostroids_rank - COALESCE(c.totallostroids_rank, 0),
                                      totalroundroids_growth = t.totalroundroids - COALESCE(c.totalroundroids, 0),
                                      totalroundroids_growth_pc = CASE WHEN (c.totalroundroids != 0) THEN COALESCE((t.totalroundroids - c.totalroundroids) * 100.0 / c.totalroundroids, 0) ELSE 0 END,
                                      totallostroids_growth = t.totallostroids - COALESCE(c.totallostroids, 0),
                                      totallostroids_growth_pc = CASE WHEN (c.totallostroids != 0) THEN COALESCE((t.totallostroids - c.totallostroids) * 100.0 / c.totallostroids, 0) ELSE 0 END,
                                 """ ) +
                                 """
                                      ticksroiding = COALESCE(c.ticksroiding, 0) + CASE WHEN (t.size > c.size AND (t.size - c.size) != (t.xp - c.xp)) THEN 1 ELSE 0 END,
                                      ticksroided = COALESCE(c.ticksroided, 0) + CASE WHEN (t.size < c.size) THEN 1 ELSE 0 END,
                                      tickroids = COALESCE(c.tickroids, 0) + t.size,
                                      avroids = COALESCE((c.tickroids + t.size) / (c.age + 1.0), t.size),
                                      roidxp = CASE WHEN (t.size != 0) THEN t.xp * 1.0 / t.size ELSE 0 END,
                                 """ + ((
                                 """
                                      %s_highest_rank = CASE WHEN (t.%s_rank <= COALESCE(c.%s_highest_rank, t.%s_rank)) THEN t.%s_rank ELSE c.%s_highest_rank END,
                                      %s_highest_rank_tick = CASE WHEN (t.%s_rank <= COALESCE(c.%s_highest_rank, t.%s_rank)) THEN :tick ELSE c.%s_highest_rank_tick END,
                                      %s_lowest_rank = CASE WHEN (t.%s_rank >= COALESCE(c.%s_lowest_rank, t.%s_rank)) THEN t.%s_rank ELSE c.%s_lowest_rank END,
                                      %s_lowest_rank_tick = CASE WHEN (t.%s_rank >= COALESCE(c.%s_lowest_rank, t.%s_rank)) THEN :tick ELSE c.%s_lowest_rank_tick END,
                                 """ * 4) % (("size",)*22 + ("score",)*22 + ("value",)*22 + ("xp",)*22)) +
                                 """
                                      totalroundroids = t.totalroundroids, totallostroids = t.totallostroids,
                                      totalroundroids_rank = t.totalroundroids_rank, totallostroids_rank = t.totallostroids_rank,
                                      size_rank = t.size_rank, score_rank = t.score_rank, value_rank = t.value_rank, xp_rank = t.xp_rank,
                                      vdiff = COALESCE(t.value - c.value, 0),
                                      sdiff = COALESCE(t.score - c.score, 0),
                                      xdiff = COALESCE(t.xp - c.xp, 0),
                                      rdiff = COALESCE(t.size - c.size, 0),
                                      mdiff = COALESCE(t.count - c.members, 0),
                                      vrankdiff = COALESCE(t.value_rank - c.value_rank, 0),
                                      srankdiff = COALESCE(t.score_rank - c.score_rank, 0),
                                      xrankdiff = COALESCE(t.xp_rank - c.xp_rank, 0),
                                      rrankdiff = COALESCE(t.size_rank - c.size_rank, 0),
                                      idle = CASE WHEN ((t.value-c.value) BETWEEN (c.vdiff-1) AND (c.vdiff+1) AND (c.xp-t.xp=0)) THEN 1 + COALESCE(c.idle, 0) ELSE 0 END
                                    FROM (SELECT *,
                                      rank() OVER (ORDER BY totalroundroids DESC) AS totalroundroids_rank,
                                      rank() OVER (ORDER BY totallostroids DESC) AS totallostroids_rank,
                                      rank() OVER (ORDER BY size DESC) AS size_rank,
                                      rank() OVER (ORDER BY score DESC) AS score_rank,
                                      rank() OVER (ORDER BY value DESC) AS value_rank,
                                      rank() OVER (ORDER BY xp DESC) AS xp_rank
                                    FROM (SELECT t.*,
                                      COALESCE(c.totalroundroids + (GREATEST(t.size - c.size, 0)), t.size) AS totalroundroids,
                                      COALESCE(c.totallostroids + (GREATEST(c.size - t.size, 0)), 0) AS totallostroids
                                    FROM cluster AS c, (SELECT x,
                                      count(*) as count,
                                      sum(size) as size,
                                      sum(value) as value,
                                      sum(score) as score,
                                      sum(xp) as xp
                                    FROM planet_temp
                                      GROUP BY x) AS t
                                      WHERE c.x = t.x) AS t) AS t
                                    WHERE c.x = t.x
                                    AND c.active = :true
                                ;""", bindparams=[tick, true]))
    
            t2=time.time()-t1
            excaliburlog("Update clusters from temp and generate ranks in %.3f seconds" % (t2,))
            t1=time.time()
    
    # We do galaxies before planets now in order to satisfy the planet(x,y) FK
    
    # ########################################################################### #
    # ##############################    GALAXIES    ############################# #
    # ########################################################################### #
    
            # Update the newly dumped data with IDs from the current data
            #  based on an x,y match in the two tables (and active=True)
            session.execute(text("""UPDATE galaxy_temp AS t SET
                                      id = g.id
                                    FROM (SELECT id, x, y FROM galaxy) AS g
                                      WHERE t.x = g.x AND t.y = g.y
                                ;"""))
    
            # Make sure all the galaxies are active,
            #  some might have been deactivated previously
            session.execute(text("UPDATE galaxy SET active = :true;", bindparams=[true]))
    
            t2=time.time()-t1
            excaliburlog("Copy galaxy ids to temp and activate in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Any galaxies in the temp table without an id are new
            # Insert them to the current table and the id(serial/auto_increment)
            #  will be generated, and we can then copy it back to the temp table
            # Galaxies under a certain amount of planets are private
            session.execute(text("INSERT INTO galaxy (x, y, active) SELECT g.x, g.y, :true FROM galaxy_temp as g WHERE g.id IS NULL;", bindparams=[true]))
            session.execute(text("UPDATE galaxy_temp SET id = (SELECT id FROM galaxy WHERE galaxy.x = galaxy_temp.x AND galaxy.y = galaxy_temp.y AND galaxy.active = :true ORDER BY galaxy.id DESC) WHERE id IS NULL;", bindparams=[true]))
    
            # For galaxies that are no longer present in the new dump
            session.execute(text("UPDATE galaxy SET active = :false WHERE id NOT IN (SELECT id FROM galaxy_temp WHERE id IS NOT NULL);", bindparams=[false]))
    
            t2=time.time()-t1
            excaliburlog("Deactivate old galaxies and generate new galaxy ids in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Update everything from the temp table and generate ranks
            # Deactivated items are untouched but NULLed earlier
            session.execute(text("""UPDATE galaxy AS g SET
                                      age = COALESCE(g.age, 0) + 1,
                                      x = t.x, y = t.y,
                                      name = t.name, size = t.size, score = t.score, value = t.value, xp = t.xp,
                                      ratio = CASE WHEN (t.value != 0) THEN 10000.0 * t.size / t.value ELSE 0 END,
                                      members = p.count,
                                      private = p.count <= :priv_gal OR (g.x = 1 AND g.y = 1),
                                 """ + (
                                 """
                                      size_growth = t.size - COALESCE(g.size - g.size_growth, 0),
                                      score_growth = t.score - COALESCE(g.score - g.score_growth, 0),
                                      value_growth = t.value - COALESCE(g.value - g.value_growth, 0),
                                      xp_growth = t.xp - COALESCE(g.xp - g.xp_growth, 0),
                                      member_growth = p.count - COALESCE(g.members - g.member_growth, 0),
                                      size_growth_pc = CASE WHEN (g.size - g.size_growth != 0) THEN COALESCE((t.size - (g.size - g.size_growth)) * 100.0 / (g.size - g.size_growth), 0) ELSE 0 END,
                                      score_growth_pc = CASE WHEN (g.score - g.score_growth != 0) THEN COALESCE((t.score - (g.score - g.score_growth)) * 100.0 / (g.score - g.score_growth), 0) ELSE 0 END,
                                      value_growth_pc = CASE WHEN (g.value - g.value_growth != 0) THEN COALESCE((t.value - (g.value - g.value_growth)) * 100.0 / (g.value - g.value_growth), 0) ELSE 0 END,
                                      xp_growth_pc = CASE WHEN (g.xp - g.xp_growth != 0) THEN COALESCE((t.xp - (g.xp - g.xp_growth)) * 100.0 / (g.xp - g.xp_growth), 0) ELSE 0 END,
                                      size_rank_change = t.size_rank - COALESCE(g.size_rank - g.size_rank_change, 0),
                                      score_rank_change = t.score_rank - COALESCE(g.score_rank - g.score_rank_change, 0),
                                      value_rank_change = t.value_rank - COALESCE(g.value_rank - g.value_rank_change, 0),
                                      xp_rank_change = t.xp_rank - COALESCE(g.xp_rank - g.xp_rank_change, 0),
                                      real_score_growth = p.real_score - COALESCE(g.real_score - g.real_score_growth, 0),
                                      real_score_growth_pc = CASE WHEN (g.real_score - g.real_score_growth != 0) THEN COALESCE((p.real_score - (g.real_score - g.real_score_growth)) * 100.0 / (g.real_score - g.real_score_growth), 0) ELSE 0 END,
                                      real_score_rank_change = p.real_score_rank - COALESCE(g.real_score_rank - g.real_score_rank_change, 0),
                                      totalroundroids_rank_change = t.totalroundroids_rank - COALESCE(g.totalroundroids_rank - g.totalroundroids_rank_change, 0),
                                      totallostroids_rank_change = t.totallostroids_rank - COALESCE(g.totallostroids_rank - g.totallostroids_rank_change, 0),
                                      totalroundroids_growth = t.totalroundroids - COALESCE(g.totalroundroids - g.totalroundroids_growth, 0),
                                      totalroundroids_growth_pc = CASE WHEN (g.totalroundroids - g.totalroundroids_growth != 0) THEN COALESCE((t.totalroundroids - (g.totalroundroids - g.totalroundroids_growth)) * 100.0 / (g.totalroundroids - g.totalroundroids_growth), 0) ELSE 0 END,
                                      totallostroids_growth = t.totallostroids - COALESCE(g.totallostroids - g.totallostroids_growth, 0),
                                      totallostroids_growth_pc = CASE WHEN (g.totallostroids - g.totallostroids_growth != 0) THEN COALESCE((t.totallostroids - (g.totallostroids - g.totallostroids_growth)) * 100.0 / (g.totallostroids - g.totallostroids_growth), 0) ELSE 0 END,
                                 """ if not midnight
                                     else
                                 """
                                      size_growth = t.size - COALESCE(g.size, 0),
                                      score_growth = t.score - COALESCE(g.score, 0),
                                      value_growth = t.value - COALESCE(g.value, 0),
                                      xp_growth = t.xp - COALESCE(g.xp, 0),
                                      member_growth = p.count - COALESCE(g.members, 0),
                                      size_growth_pc = CASE WHEN (g.size != 0) THEN COALESCE((t.size - g.size) * 100.0 / g.size, 0) ELSE 0 END,
                                      score_growth_pc = CASE WHEN (g.score != 0) THEN COALESCE((t.score - g.score) * 100.0 / g.score * 100, 0) ELSE 0 END,
                                      value_growth_pc = CASE WHEN (g.value != 0) THEN COALESCE((t.value - g.value) * 100.0 / g.value, 0) ELSE 0 END,
                                      xp_growth_pc = CASE WHEN (g.xp != 0) THEN COALESCE((t.xp - g.xp) * 100.0 / g.xp, 0) ELSE 0 END,
                                      size_rank_change = t.size_rank - COALESCE(g.size_rank, 0),
                                      score_rank_change = t.score_rank - COALESCE(g.score_rank, 0),
                                      value_rank_change = t.value_rank - COALESCE(g.value_rank, 0),
                                      xp_rank_change = t.xp_rank - COALESCE(g.xp_rank, 0),
                                      real_score_growth = p.real_score - COALESCE(g.real_score, 0),
                                      real_score_growth_pc = CASE WHEN (g.real_score != 0) THEN COALESCE((p.real_score - g.real_score) * 100.0 / g.real_score * 100, 0) ELSE 0 END,
                                      real_score_rank_change = p.real_score_rank - COALESCE(g.real_score_rank, 0),
                                      totalroundroids_rank_change = t.totalroundroids_rank - COALESCE(g.totalroundroids_rank, 0),
                                      totallostroids_rank_change = t.totallostroids_rank - COALESCE(g.totallostroids_rank, 0),
                                      totalroundroids_growth = t.totalroundroids - COALESCE(g.totalroundroids, 0),
                                      totalroundroids_growth_pc = CASE WHEN (g.totalroundroids != 0) THEN COALESCE((t.totalroundroids - g.totalroundroids) * 100.0 / g.totalroundroids, 0) ELSE 0 END,
                                      totallostroids_growth = t.totallostroids - COALESCE(g.totallostroids, 0),
                                      totallostroids_growth_pc = CASE WHEN (g.totallostroids != 0) THEN COALESCE((t.totallostroids - g.totallostroids) * 100.0 / g.totallostroids, 0) ELSE 0 END,
                                 """ ) +
                                 """
                                      ticksroiding = COALESCE(g.ticksroiding, 0) + CASE WHEN (t.size > g.size AND (t.size - g.size) != (t.xp - g.xp)) THEN 1 ELSE 0 END,
                                      ticksroided = COALESCE(g.ticksroided, 0) + CASE WHEN (t.size < g.size) THEN 1 ELSE 0 END,
                                      tickroids = COALESCE(g.tickroids, 0) + t.size,
                                      avroids = COALESCE((g.tickroids + t.size) / (g.age + 1.0), t.size),
                                      roidxp = CASE WHEN (t.size != 0) THEN t.xp * 1.0 / t.size ELSE 0 END,
                                 """ + ((
                                 """
                                      %s_highest_rank = CASE WHEN (t.%s_rank <= COALESCE(g.%s_highest_rank, t.%s_rank)) THEN t.%s_rank ELSE g.%s_highest_rank END,
                                      %s_highest_rank_tick = CASE WHEN (t.%s_rank <= COALESCE(g.%s_highest_rank, t.%s_rank)) THEN :tick ELSE g.%s_highest_rank_tick END,
                                      %s_lowest_rank = CASE WHEN (t.%s_rank >= COALESCE(g.%s_lowest_rank, t.%s_rank)) THEN t.%s_rank ELSE g.%s_lowest_rank END,
                                      %s_lowest_rank_tick = CASE WHEN (t.%s_rank >= COALESCE(g.%s_lowest_rank, t.%s_rank)) THEN :tick ELSE g.%s_lowest_rank_tick END,
                                 """ * 4) % (("size",)*22 + ("score",)*22 + ("value",)*22 + ("xp",)*22)) +
                                 """
                                      real_score_highest_rank = CASE WHEN (p.real_score_rank <= COALESCE(g.real_score_highest_rank, p.real_score_rank)) THEN p.real_score_rank ELSE g.real_score_highest_rank END,
                                      real_score_highest_rank_tick = CASE WHEN (p.real_score_rank <= COALESCE(g.real_score_highest_rank, p.real_score_rank)) THEN :tick ELSE g.real_score_highest_rank_tick END,
                                      real_score_lowest_rank = CASE WHEN (p.real_score_rank >= COALESCE(g.real_score_lowest_rank, p.real_score_rank)) THEN p.real_score_rank ELSE g.real_score_lowest_rank END,
                                      real_score_lowest_rank_tick = CASE WHEN (p.real_score_rank >= COALESCE(g.real_score_lowest_rank, p.real_score_rank)) THEN :tick ELSE g.real_score_lowest_rank_tick END,
                                      real_score = p.real_score, real_score_rank = p.real_score_rank,
                                      totalroundroids = t.totalroundroids, totallostroids = t.totallostroids,
                                      totalroundroids_rank = t.totalroundroids_rank, totallostroids_rank = t.totallostroids_rank,
                                      size_rank = t.size_rank, score_rank = t.score_rank, value_rank = t.value_rank, xp_rank = t.xp_rank,
                                      vdiff = COALESCE(t.value - g.value, 0),
                                      sdiff = COALESCE(t.score - g.score, 0),
                                      rsdiff = COALESCE(p.real_score - g.real_score, 0),
                                      xdiff = COALESCE(t.xp - g.xp, 0),
                                      rdiff = COALESCE(t.size - g.size, 0),
                                      mdiff = COALESCE(p.count - g.members, 0),
                                      vrankdiff = COALESCE(t.value_rank - g.value_rank, 0),
                                      srankdiff = COALESCE(t.score_rank - g.score_rank, 0),
                                      rsrankdiff = COALESCE(p.real_score_rank - g.real_score_rank, 0),
                                      xrankdiff = COALESCE(t.xp_rank - g.xp_rank, 0),
                                      rrankdiff = COALESCE(t.size_rank - g.size_rank, 0),
                                      idle = CASE WHEN ((t.value-g.value) BETWEEN (g.vdiff-1) AND (g.vdiff+1) AND (g.xp-t.xp=0)) THEN 1 + COALESCE(g.idle, 0) ELSE 0 END
                                    FROM (SELECT *,
                                      rank() OVER (ORDER BY totalroundroids DESC) AS totalroundroids_rank,
                                      rank() OVER (ORDER BY totallostroids DESC) AS totallostroids_rank,
                                      rank() OVER (ORDER BY size DESC) AS size_rank,
                                      rank() OVER (ORDER BY score DESC) AS score_rank,
                                      rank() OVER (ORDER BY value DESC) AS value_rank,
                                      rank() OVER (ORDER BY xp DESC) AS xp_rank
                                    FROM (SELECT t.*,
                                      COALESCE(g.totalroundroids + (GREATEST(t.size - g.size, 0)), t.size) AS totalroundroids,
                                      COALESCE(g.totallostroids + (GREATEST(g.size - t.size, 0)), 0) AS totallostroids
                                    FROM galaxy AS g, galaxy_temp AS t
                                      WHERE g.id = t.id AND g.active = :true) AS t) AS t,
                                      (SELECT a.x, a.y, a.count, a.real_score,
                                        rank() OVER (ORDER BY a.real_score DESC) AS real_score_rank
                                      FROM (SELECT x, y,
                                          count(*) AS count,
                                          sum(score) AS real_score
                                        FROM planet_temp
                                        GROUP BY x, y
                                        ) AS a
                                      ) AS p
                                    WHERE g.id = t.id
                                       AND g.x = p.x AND g.y = p.y
                                    AND g.active = :true
                                ;""", bindparams=[tick, true, bindparam("priv_gal",PA.getint("numbers", "priv_gal"))]))
    
            t2=time.time()-t1
            excaliburlog("Update galaxies from temp and generate ranks in %.3f seconds" % (t2,))
            t1=time.time()
    
    # ########################################################################### #
    # ##############################    PLANETS    ############################## #
    # ########################################################################### #
    
            # Update the newly dumped data with IDs from the current data
            #  based on an ruler-,planet-name match in the two tables (and active=True)
            session.execute(text("""UPDATE planet_temp AS t SET
                                      id = p.id
                                    FROM (SELECT id, rulername, planetname FROM planet WHERE active = :true) AS p
                                      WHERE t.rulername = p.rulername AND t.planetname = p.planetname
                                ;""", bindparams=[true]))
    
            t2=time.time()-t1
            excaliburlog("Copy planet ids to temp in %.3f seconds" % (t2,))
            t1=time.time()
    
            while last_tick > PA.getint("numbers", "shuffle"): #looks are deceiving, this only runs once
                # This code is designed to match planets whose ruler/planet names
                #  change, by matching them with new planets using certain criteria
    
                def load_planet_id_search():
                    # If we have any ids in the planet_new_id_search table,
                    #  match them up with planet_temp using x,y,z
                    session.execute(text("UPDATE planet_temp SET id = (SELECT id FROM planet_new_id_search WHERE planet_temp.x = planet_new_id_search.x AND planet_temp.y = planet_new_id_search.y AND planet_temp.z = planet_new_id_search.z) WHERE id IS NULL;"))
                    # Empty out the two search tables
                    session.execute(planet_new_id_search.delete())
                    session.execute(planet_old_id_search.delete())
                    # Insert from the new tick any planets without id
                    if session.execute(text("INSERT INTO planet_new_id_search SELECT id, x, y, z, planetname, rulername, race, size, score, value, xp FROM planet_temp WHERE planet_temp.id IS NULL;")).rowcount < 1:
                        return None
                    # Insert from the previous tick any planets without
                    #  an equivalent planet from the new tick
                    if session.execute(text("INSERT INTO planet_old_id_search SELECT id, x, y, z, planetname, rulername, race, size, score, value, xp, vdiff FROM planet WHERE planet.id NOT IN (SELECT id FROM planet_temp WHERE id IS NOT NULL) AND planet.active = :true;", bindparams=[true])).rowcount < 1:
                        return None
                    # If either of the two search tables do not have any planets
                    #  to match moved in (.rowcount() < 1) then return None, else:
                    return 1
    
                # Load in the planets to match against and use the first set of match criterion
                if load_planet_id_search() is None: break
                session.execute(text("""UPDATE planet_new_id_search SET id = (
                                          SELECT id FROM planet_old_id_search WHERE
                                            planet_old_id_search.x = planet_new_id_search.x AND
                                            planet_old_id_search.y = planet_new_id_search.y AND
                                            planet_old_id_search.z = planet_new_id_search.z AND
                                            planet_old_id_search.race = planet_new_id_search.race AND
                                            planet_old_id_search.size > 500 AND
                                            planet_old_id_search.size = planet_new_id_search.size
                                          );"""))
                # As above, second set of criterion
                if load_planet_id_search() is None: break
                session.execute(text("""UPDATE planet_new_id_search SET id = (
                                          SELECT id FROM planet_old_id_search WHERE
                                            planet_old_id_search.x = planet_new_id_search.x AND
                                            planet_old_id_search.y = planet_new_id_search.y AND
                                            planet_old_id_search.z = planet_new_id_search.z AND
                                            planet_old_id_search.race = planet_new_id_search.race AND
                                            planet_old_id_search.value > 500000 AND
                                            planet_new_id_search.value BETWEEN
                                                    planet_old_id_search.value - (2* planet_old_id_search.vdiff) AND 
                                                    planet_old_id_search.value + (2* planet_old_id_search.vdiff)
                                          );"""))
                # Third set of criterion
                if load_planet_id_search() is None: break
                session.execute(text("""UPDATE planet_new_id_search SET id = (
                                          SELECT id FROM planet_old_id_search WHERE
                                            planet_old_id_search.race = planet_new_id_search.race AND
                                            planet_old_id_search.size > 500 AND
                                            planet_old_id_search.size = planet_new_id_search.size AND
                                            planet_old_id_search.value > 500000 AND
                                            planet_new_id_search.value BETWEEN
                                                    planet_old_id_search.value - (2* planet_old_id_search.vdiff) AND
                                                    planet_old_id_search.value + (2* planet_old_id_search.vdiff)
                                          );"""))
                # Fourth set of criterion for smaller planets
                if load_planet_id_search() is None: break
                session.execute(text("""UPDATE planet_new_id_search SET id = (
                                          SELECT id FROM planet_old_id_search WHERE
                                            planet_old_id_search.x = planet_new_id_search.x AND
                                            planet_old_id_search.y = planet_new_id_search.y AND
                                            planet_old_id_search.z = planet_new_id_search.z AND
                                            planet_old_id_search.race = planet_new_id_search.race AND
                                            planet_old_id_search.size = planet_new_id_search.size AND
                                            planet_new_id_search.value BETWEEN
                                                    planet_old_id_search.value - (2* planet_old_id_search.vdiff) AND
                                                    planet_old_id_search.value + (2* planet_old_id_search.vdiff)
                                          );"""))
                # Fifth set of criterion for planets that half-match
                if load_planet_id_search() is None: break
                session.execute(text("""UPDATE planet_new_id_search SET id = (
                                          SELECT id FROM planet_old_id_search WHERE
                                            planet_old_id_search.x = planet_new_id_search.x AND
                                            planet_old_id_search.y = planet_new_id_search.y AND
                                            planet_old_id_search.z = planet_new_id_search.z AND
                                            (planet_old_id_search.planetname = planet_new_id_search.planetname
                                             OR planet_old_id_search.rulername = planet_new_id_search.rulername)
                                          );"""))
                # Final update
                if load_planet_id_search() is None: break
                break
    
            t2=time.time()-t1
            excaliburlog("Lost planet ids match up in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Any planets in the temp table without an id are new
            # Insert them to the current table and the id(serial/auto_increment)
            #  will be generated, and we can then copy it back to the temp table
            session.execute(text("INSERT INTO planet (rulername, planetname, active) SELECT rulername, planetname, :true FROM planet_temp WHERE id IS NULL;", bindparams=[true]))
            session.execute(text("UPDATE planet_temp SET id = (SELECT id FROM planet WHERE planet.rulername = planet_temp.rulername AND planet.planetname = planet_temp.planetname AND planet.active = :true ORDER BY planet.id DESC) WHERE id IS NULL;", bindparams=[true]))
    
            t2=time.time()-t1
            excaliburlog("Generate new planet ids in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Create records of new planets,
            session.execute(text("""INSERT INTO planet_exiles (hour, tick, id, newx, newy, newz)
                                    SELECT :hour, :tick, planet.id, planet_temp.x, planet_temp.y, planet_temp.z
                                    FROM planet_temp, planet
                                    WHERE
                                        planet.rulername = planet_temp.rulername AND
                                        planet.planetname = planet_temp.planetname AND
                                        planet.active = :true AND
                                        planet.age IS NULL
                                ;""", bindparams=[tick, hour, true]))
            # deleted plantes
            session.execute(text("""INSERT INTO planet_exiles (hour, tick, id, oldx, oldy, oldz)
                                    SELECT :hour, :tick, planet.id, planet.x, planet.y, planet.z
                                    FROM planet
                                    WHERE
                                        planet.active = :true AND
                                        planet.age IS NOT NULL AND
                                        planet.id NOT IN (SELECT id FROM planet_temp WHERE id IS NOT NULL)
                                ;""", bindparams=[tick, hour, true]))
            # planet renames
            session.execute(text("""INSERT INTO planet_exiles (hour, tick, id, oldx, oldy, oldz, newx, newy, newz)
                                    SELECT :hour, :tick, planet.id, planet.x, planet.y, planet.z, planet_temp.x, planet_temp.y, planet_temp.z
                                    FROM planet_temp, planet
                                    WHERE
                                        planet.id = planet_temp.id AND
                                        planet.active = :true AND
                                        planet.age IS NOT NULL AND
                                        (planet.rulername != planet_temp.rulername OR planet.planetname != planet_temp.planetname)
                                ;""", bindparams=[tick, hour, true]))
            # and planet movements
            session.execute(text("""INSERT INTO planet_exiles (hour, tick, id, oldx, oldy, oldz, newx, newy, newz)
                                    SELECT :hour, :tick, planet.id, planet.x, planet.y, planet.z, planet_temp.x, planet_temp.y, planet_temp.z
                                    FROM planet_temp, planet
                                    WHERE
                                        planet.id = planet_temp.id AND
                                        planet.active = :true AND
                                        planet.age IS NOT NULL AND
                                        (planet.x != planet_temp.x OR planet.y != planet_temp.y OR planet.z != planet_temp.z)
                                ;""", bindparams=[tick, hour, true]))
    
            t2=time.time()-t1
            excaliburlog("Track new/deleted/moved planets in %.3f seconds" % (t2,))
            t1=time.time()
    
            # For planets that are no longer present in the new dump
            session.execute(text("UPDATE planet SET active = :false WHERE id NOT IN (SELECT id FROM planet_temp WHERE id IS NOT NULL);", bindparams=[false]))
    
            t2=time.time()-t1
            excaliburlog("Deactivate old planets in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Update everything from the temp table and generate ranks
            # Deactivated items are untouched but NULLed earlier
            session.execute(text("""UPDATE planet AS p SET
                                      age = COALESCE(p.age, 0) + 1,
                                      x = t.x, y = t.y, z = t.z,
                                      planetname = t.planetname, rulername = t.rulername, race = t.race,
                                      size = t.size, score = t.score, value = t.value, xp = t.xp,
                                      ratio = CASE WHEN (t.value != 0) THEN 10000.0 * t.size / t.value ELSE 0 END,
                                 """ + ((
                                 """
                                      size_growth = t.size - COALESCE(p.size - p.size_growth, 0),
                                      score_growth = t.score - COALESCE(p.score - p.score_growth, 0),
                                      value_growth = t.value - COALESCE(p.value - p.value_growth, 0),
                                      xp_growth = t.xp - COALESCE(p.xp - p.xp_growth, 0),
                                      size_growth_pc = CASE WHEN (p.size - p.size_growth != 0) THEN COALESCE((t.size - (p.size - p.size_growth)) * 100.0 / (p.size - p.size_growth), 0) ELSE 0 END,
                                      score_growth_pc = CASE WHEN (p.score - p.score_growth != 0) THEN COALESCE((t.score - (p.score - p.score_growth)) * 100.0 / (p.score - p.score_growth), 0) ELSE 0 END,
                                      value_growth_pc = CASE WHEN (p.value - p.value_growth != 0) THEN COALESCE((t.value - (p.value - p.value_growth)) * 100.0 / (p.value - p.value_growth), 0) ELSE 0 END,
                                      xp_growth_pc = CASE WHEN (p.xp - p.xp_growth != 0) THEN COALESCE((t.xp - (p.xp - p.xp_growth)) * 100.0 / (p.xp - p.xp_growth), 0) ELSE 0 END,
                                 """ + ((
                                 """
                                      %ssize_rank_change = t.%ssize_rank - COALESCE(p.%ssize_rank - p.%ssize_rank_change, 0),
                                      %sscore_rank_change = t.%sscore_rank - COALESCE(p.%sscore_rank - p.%sscore_rank_change, 0),
                                      %svalue_rank_change = t.%svalue_rank - COALESCE(p.%svalue_rank - p.%svalue_rank_change, 0),
                                      %sxp_rank_change = t.%sxp_rank - COALESCE(p.%sxp_rank - p.%sxp_rank_change, 0),
                                      %stotalroundroids_rank_change = t.%stotalroundroids_rank - COALESCE(p.%stotalroundroids_rank - p.%stotalroundroids_rank_change, 0),
                                      %stotallostroids_rank_change = t.%stotallostroids_rank - COALESCE(p.%stotallostroids_rank - p.%stotallostroids_rank_change, 0),
                                 """ * 4) % (("",)*24 + ("cluster_",)*24 + ("galaxy_",)*24 + ("race_",)*24)) +
                                 """
                                      totalroundroids_growth = t.totalroundroids - COALESCE(p.totalroundroids - p.totalroundroids_growth, 0),
                                      totalroundroids_growth_pc = CASE WHEN (p.totalroundroids - p.totalroundroids_growth != 0) THEN COALESCE((t.totalroundroids - (p.totalroundroids - p.totalroundroids_growth)) * 100.0 / (p.totalroundroids - p.totalroundroids_growth), 0) ELSE 0 END,
                                      totallostroids_growth = t.totallostroids - COALESCE(p.totallostroids - p.totallostroids_growth, 0),
                                      totallostroids_growth_pc = CASE WHEN (p.totallostroids - p.totallostroids_growth != 0) THEN COALESCE((t.totallostroids - (p.totallostroids - p.totallostroids_growth)) * 100.0 / (p.totallostroids - p.totallostroids_growth), 0) ELSE 0 END,
                                 """ ) if not midnight
                                     else (
                                 """
                                      size_growth = t.size - COALESCE(p.size, 0),
                                      score_growth = t.score - COALESCE(p.score, 0),
                                      value_growth = t.value - COALESCE(p.value, 0),
                                      xp_growth = t.xp - COALESCE(p.xp, 0),
                                      size_growth_pc = CASE WHEN (p.size != 0) THEN COALESCE((t.size - p.size) * 100.0 / p.size, 0) ELSE 0 END,
                                      score_growth_pc = CASE WHEN (p.score != 0) THEN COALESCE((t.score - p.score) * 100.0 / p.score, 0) ELSE 0 END,
                                      value_growth_pc = CASE WHEN (p.value != 0) THEN COALESCE((t.value - p.value) * 100.0 / p.value, 0) ELSE 0 END,
                                      xp_growth_pc = CASE WHEN (p.xp != 0) THEN COALESCE((t.xp - p.xp) * 100.0 / p.xp, 0) ELSE 0 END,
                                 """ + ((
                                 """
                                      %ssize_rank_change = t.%ssize_rank - COALESCE(p.%ssize_rank, 0),
                                      %sscore_rank_change = t.%sscore_rank - COALESCE(p.%sscore_rank, 0),
                                      %svalue_rank_change = t.%svalue_rank - COALESCE(p.%svalue_rank, 0),
                                      %sxp_rank_change = t.%sxp_rank - COALESCE(p.%sxp_rank, 0),
                                      %stotalroundroids_rank_change = t.%stotalroundroids_rank - COALESCE(p.%stotalroundroids_rank, 0),
                                      %stotallostroids_rank_change = t.%stotallostroids_rank - COALESCE(p.%stotallostroids_rank, 0),
                                 """ * 4) % (("",)*18 + ("cluster_",)*18 + ("galaxy_",)*18 + ("race_",)*18)) +
                                 """
                                      totalroundroids_growth = t.totalroundroids - COALESCE(p.totalroundroids, 0),
                                      totalroundroids_growth_pc = CASE WHEN (p.totalroundroids != 0) THEN COALESCE((t.totalroundroids - p.totalroundroids) * 100.0 / p.totalroundroids, 0) ELSE 0 END,
                                      totallostroids_growth = t.totallostroids - COALESCE(p.totallostroids, 0),
                                      totallostroids_growth_pc = CASE WHEN (p.totallostroids != 0) THEN COALESCE((t.totallostroids - p.totallostroids) * 100.0 / p.totallostroids, 0) ELSE 0 END,
                                 """ )) +
                                 """
                                      totalroundroids = t.totalroundroids, totallostroids = t.totallostroids,
                                 """ + ((
                                 """
                                      %ssize_rank = t.%ssize_rank, %sscore_rank = t.%sscore_rank, %svalue_rank = t.%svalue_rank, %sxp_rank = t.%sxp_rank,
                                      %stotalroundroids_rank = t.%stotalroundroids_rank, %stotallostroids_rank = t.%stotallostroids_rank,
                                 """ * 4) % (("",)*12 + ("cluster_",)*12 + ("galaxy_",)*12 + ("race_",)*12)) +
                                 """
                                      ticksroiding = COALESCE(p.ticksroiding, 0) + CASE WHEN (t.size > p.size AND (t.size - p.size) != (t.xp - p.xp)) THEN 1 ELSE 0 END,
                                      ticksroided = COALESCE(p.ticksroided, 0) + CASE WHEN (t.size < p.size) THEN 1 ELSE 0 END,
                                      tickroids = COALESCE(p.tickroids, 0) + t.size,
                                      avroids = COALESCE((p.tickroids + t.size) / (p.age + 1.0), t.size),
                                      roidxp = CASE WHEN (t.size != 0) THEN t.xp * 1.0 / t.size ELSE 0 END,
                                 """ + ((
                                 """
                                      %s_highest_rank = CASE WHEN (t.%s_rank <= COALESCE(p.%s_highest_rank, t.%s_rank)) THEN t.%s_rank ELSE p.%s_highest_rank END,
                                      %s_highest_rank_tick = CASE WHEN (t.%s_rank <= COALESCE(p.%s_highest_rank, t.%s_rank)) THEN :tick ELSE p.%s_highest_rank_tick END,
                                      %s_lowest_rank = CASE WHEN (t.%s_rank >= COALESCE(p.%s_lowest_rank, t.%s_rank)) THEN t.%s_rank ELSE p.%s_lowest_rank END,
                                      %s_lowest_rank_tick = CASE WHEN (t.%s_rank >= COALESCE(p.%s_lowest_rank, t.%s_rank)) THEN :tick ELSE p.%s_lowest_rank_tick END,
                                 """ * 4) % (("size",)*22 + ("score",)*22 + ("value",)*22 + ("xp",)*22)) +
                                 """
                                      vdiff = COALESCE(t.value - p.value, 0),
                                      sdiff = COALESCE(t.score - p.score, 0),
                                      xdiff = COALESCE(t.xp - p.xp, 0),
                                      rdiff = COALESCE(t.size - p.size, 0),
                                      vrankdiff = COALESCE(t.value_rank - p.value_rank, 0),
                                      srankdiff = COALESCE(t.score_rank - p.score_rank, 0),
                                      xrankdiff = COALESCE(t.xp_rank - p.xp_rank, 0),
                                      rrankdiff = COALESCE(t.size_rank - p.size_rank, 0),
                                      idle = CASE WHEN ((t.value-p.value) BETWEEN (p.vdiff-1) AND (p.vdiff+1) AND (p.xp-t.xp=0)) THEN 1 + COALESCE(p.idle, 0) ELSE 0 END
                                    FROM (SELECT *,
                                 """ + ((
                                 """
                                      rank() OVER (PARTITION BY %s ORDER BY totalroundroids DESC) AS %s_totalroundroids_rank,
                                      rank() OVER (PARTITION BY %s ORDER BY totallostroids DESC) AS %s_totallostroids_rank,
                                      rank() OVER (PARTITION BY %s ORDER BY size DESC) AS %s_size_rank,
                                      rank() OVER (PARTITION BY %s ORDER BY score DESC) AS %s_score_rank,
                                      rank() OVER (PARTITION BY %s ORDER BY value DESC) AS %s_value_rank,
                                      rank() OVER (PARTITION BY %s ORDER BY xp DESC) AS %s_xp_rank,
                                 """ * 3) % (("x","cluster",)*6 + ("x, y","galaxy",)*6 + ("race","race",)*6)) +
                                 """
                                      rank() OVER (ORDER BY totalroundroids DESC) AS totalroundroids_rank,
                                      rank() OVER (ORDER BY totallostroids DESC) AS totallostroids_rank,
                                      rank() OVER (ORDER BY size DESC) AS size_rank,
                                      rank() OVER (ORDER BY score DESC) AS score_rank,
                                      rank() OVER (ORDER BY value DESC) AS value_rank,
                                      rank() OVER (ORDER BY xp DESC) AS xp_rank
                                    FROM (SELECT t.*,
                                      COALESCE(p.totalroundroids + (GREATEST(t.size - p.size, 0)), t.size) AS totalroundroids,
                                      COALESCE(p.totallostroids + (GREATEST(p.size - t.size, 0)), 0) AS totallostroids
                                    FROM planet AS p, planet_temp AS t
                                      WHERE p.id = t.id AND p.active = :true) AS t) AS t
                                      WHERE p.id = t.id
                                    AND p.active = :true
                                ;""", bindparams=[tick, true]))
    
            t2=time.time()-t1
            excaliburlog("Update planets from temp and generate ranks in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Idle data
            session.execute(text("""INSERT INTO planet_idles (hour, tick, id, idle)
                                    SELECT :hour, :tick, planet.id, planet.idle
                                    FROM planet
                                    WHERE
                                        planet.idle > 0 AND
                                        planet.active = :true
                                ;""", bindparams=[tick, hour, true]))
            # Value drops
            session.execute(text("""INSERT INTO planet_value_drops (hour, tick, id, vdiff)
                                    SELECT :hour, :tick, planet.id, planet.vdiff
                                    FROM planet
                                    WHERE
                                        planet.vdiff < 0 AND
                                        planet.active = :true
                                ;""", bindparams=[tick, hour, true]))
            # Landings
            session.execute(text("""INSERT INTO planet_landings (hour, tick, id, rdiff)
                                    SELECT :hour, :tick, planet.id, planet.rdiff
                                    FROM planet
                                    WHERE
                                        planet.rdiff > 0 AND
                                        planet.rdiff != planet.xdiff AND
                                        planet.active = :true
                                ;""", bindparams=[tick, hour, true]))
            # Landed on
            session.execute(text("""INSERT INTO planet_landed_on (hour, tick, id, rdiff)
                                    SELECT :hour, :tick, planet.id, planet.rdiff
                                    FROM planet
                                    WHERE
                                        planet.rdiff < 0 AND
                                        planet.active = :true
                                ;""", bindparams=[tick, hour, true]))
    
            t2=time.time()-t1
            excaliburlog("Planet stats in in %.3f seconds" % (t2,))
            t1=time.time()
    
    # ########################################################################### #
    # #############################    ALLIANCES    ############################# #
    # ########################################################################### #
    
            # Update the newly dumped data with IDs from the current data
            #  based on a name match in the two tables (and active=True)
            session.execute(text("""UPDATE alliance_temp AS t SET
                                      id = a.id
                                    FROM (SELECT id, name FROM alliance) AS a
                                      WHERE t.name = a.name
                                ;"""))
    
            # Make sure all the alliances are active,
            #  some might have been deactivated previously
            session.execute(text("UPDATE alliance SET active = :true;", bindparams=[true]))
    
            t2=time.time()-t1
            excaliburlog("Copy alliance ids to temp and activate in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Any alliances in the temp table without an id are new
            # Insert them to the current table and the id(serial/auto_increment)
            #  will be generated, and we can then copy it back to the temp table
            session.execute(text("INSERT INTO alliance (name, active) SELECT name, :true FROM alliance_temp WHERE id IS NULL;", bindparams=[true]))
            session.execute(text("UPDATE alliance_temp SET id = (SELECT id FROM alliance WHERE alliance.name = alliance_temp.name AND alliance.active = :true ORDER BY alliance.id DESC) WHERE id IS NULL;", bindparams=[true]))
    
            # For alliances that are no longer present in the new dump, we will
            #  NULL all the data, leaving only the name and id for FKs
            session.execute(text("UPDATE alliance SET active = :false WHERE id NOT IN (SELECT id FROM alliance_temp WHERE id IS NOT NULL);", bindparams=[false]))
    
            t2=time.time()-t1
            excaliburlog("Deactivate old alliances and generate new alliance ids in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Update everything from the temp table and generate ranks
            # Deactivated items are untouched but NULLed earlier
            session.execute(text("""UPDATE alliance AS a SET
                                      age = COALESCE(a.age, 0) + 1,
                                      size = t.size, members = t.members, score = t.score, points = t.points,
                                      score_total = t.score_total, value_total = t.value_total,
                                      size_avg = t.size_avg, score_avg = t.score_avg, points_avg = t.points_avg,
                                      ratio = CASE WHEN (t.score != 0) THEN 10000.0 * t.size / t.score ELSE 0 END,
                                 """ + (
                                 """
                                      size_growth = t.size - COALESCE(a.size - a.size_growth, 0),
                                      score_growth = t.score - COALESCE(a.score - a.score_growth, 0),
                                      points_growth = t.points - COALESCE(a.points - a.points_growth, 0),
                                      member_growth = t.members - COALESCE(a.members - a.member_growth, 0),
                                      size_growth_pc = CASE WHEN (a.size - a.size_growth != 0) THEN COALESCE((t.size - (a.size - a.size_growth)) * 100.0 / (a.size - a.size_growth), 0) ELSE 0 END,
                                      score_growth_pc = CASE WHEN (a.score - a.score_growth != 0) THEN COALESCE((t.score - (a.score - a.score_growth)) * 100.0 / (a.score - a.score_growth), 0) ELSE 0 END,
                                      points_growth_pc = CASE WHEN (a.points - a.points_growth != 0) THEN COALESCE((t.points - (a.points - a.points_growth)) * 100.0 / (a.points - a.points_growth), 0) ELSE 0 END,
                                      size_avg_growth = t.size_avg - COALESCE(a.size_avg - a.size_avg_growth, 0),
                                      score_avg_growth = t.score_avg - COALESCE(a.score_avg - a.score_avg_growth, 0),
                                      points_avg_growth = t.points_avg - COALESCE(a.points_avg - a.points_avg_growth, 0),
                                      size_avg_growth_pc = CASE WHEN (a.size_avg - a.size_avg_growth != 0) THEN COALESCE((t.size_avg - (a.size_avg - a.size_avg_growth)) * 100.0 / (a.size_avg - a.size_avg_growth), 0) ELSE 0 END,
                                      score_avg_growth_pc = CASE WHEN (a.score_avg - a.score_avg_growth != 0) THEN COALESCE((t.score_avg - (a.score_avg - a.score_avg_growth)) * 100.0 / (a.score_avg - a.score_avg_growth), 0) ELSE 0 END,
                                      points_avg_growth_pc = CASE WHEN (a.points_avg - a.points_avg_growth != 0) THEN COALESCE((t.points_avg - (a.points_avg - a.points_avg_growth)) * 100.0 / (a.points_avg - a.points_avg_growth), 0) ELSE 0 END,
                                      size_rank_change = t.size_rank - COALESCE(a.size_rank - a.size_rank_change, 0),
                                      members_rank_change = t.members_rank - COALESCE(a.members_rank - a.members_rank_change, 0),
                                      score_rank_change = t.score_rank - COALESCE(a.score_rank - a.score_rank_change, 0),
                                      points_rank_change = t.points_rank - COALESCE(a.points_rank - a.points_rank_change, 0),
                                      size_avg_rank_change = t.size_avg_rank - COALESCE(a.size_avg_rank - a.size_avg_rank_change, 0),
                                      score_avg_rank_change = t.score_avg_rank - COALESCE(a.score_avg_rank - a.score_avg_rank_change, 0),
                                      points_avg_rank_change = t.points_avg_rank - COALESCE(a.points_avg_rank - a.points_avg_rank_change, 0),
                                      totalroundroids_rank_change = t.totalroundroids_rank - COALESCE(a.totalroundroids_rank - a.totalroundroids_rank_change, 0),
                                      totallostroids_rank_change = t.totallostroids_rank - COALESCE(a.totallostroids_rank - a.totallostroids_rank_change, 0),
                                      totalroundroids_growth = t.totalroundroids - COALESCE(a.totalroundroids - a.totalroundroids_growth, 0),
                                      totalroundroids_growth_pc = CASE WHEN (a.totalroundroids - a.totalroundroids_growth != 0) THEN COALESCE((t.totalroundroids - (a.totalroundroids - a.totalroundroids_growth)) * 100.0 / (a.totalroundroids - a.totalroundroids_growth), 0) ELSE 0 END,
                                      totallostroids_growth = t.totallostroids - COALESCE(a.totallostroids - a.totallostroids_growth, 0),
                                      totallostroids_growth_pc = CASE WHEN (a.totallostroids - a.totallostroids_growth != 0) THEN COALESCE((t.totallostroids - (a.totallostroids - a.totallostroids_growth)) * 100.0 / (a.totallostroids - a.totallostroids_growth), 0) ELSE 0 END,
                                 """ if not midnight
                                     else
                                 """
                                      size_growth = t.size - COALESCE(a.size, 0),
                                      score_growth = t.score - COALESCE(a.score, 0),
                                      points_growth = t.points - COALESCE(a.points, 0),
                                      member_growth = t.members - COALESCE(a.members, 0),
                                      size_growth_pc = CASE WHEN (a.size != 0) THEN COALESCE((t.size - a.size) * 100.0 / a.size, 0) ELSE 0 END,
                                      score_growth_pc = CASE WHEN (a.score != 0) THEN COALESCE((t.score - a.score) * 100.0 / a.score, 0) ELSE 0 END,
                                      points_growth_pc = CASE WHEN (a.points != 0) THEN COALESCE((t.points - a.points) * 100.0 / a.points, 0) ELSE 0 END,
                                      size_avg_growth = t.size_avg - COALESCE(a.size_avg, 0),
                                      score_avg_growth = t.score_avg - COALESCE(a.score_avg, 0),
                                      points_avg_growth = t.points_avg - COALESCE(a.points_avg, 0),
                                      size_avg_growth_pc = CASE WHEN (a.size_avg != 0) THEN COALESCE((t.size_avg - a.size_avg) * 100.0 / a.size_avg, 0) ELSE 0 END,
                                      score_avg_growth_pc = CASE WHEN (a.score_avg != 0) THEN COALESCE((t.score_avg - a.score_avg) * 100.0 / a.score_avg, 0) ELSE 0 END,
                                      points_avg_growth_pc = CASE WHEN (a.points_avg != 0) THEN COALESCE((t.points_avg - a.points_avg) * 100.0 / a.points_avg, 0) ELSE 0 END,
                                      size_rank_change = t.size_rank - COALESCE(a.size_rank, 0),
                                      members_rank_change = t.members_rank - COALESCE(a.members_rank, 0),
                                      score_rank_change = t.score_rank - COALESCE(a.score_rank, 0),
                                      points_rank_change = t.points_rank - COALESCE(a.points_rank, 0),
                                      size_avg_rank_change = t.size_avg_rank - COALESCE(a.size_avg_rank, 0),
                                      score_avg_rank_change = t.score_avg_rank - COALESCE(a.score_avg_rank, 0),
                                      points_avg_rank_change = t.points_avg_rank - COALESCE(a.points_avg_rank, 0),
                                      totalroundroids_rank_change = t.totalroundroids_rank - COALESCE(a.totalroundroids_rank, 0),
                                      totallostroids_rank_change = t.totallostroids_rank - COALESCE(a.totallostroids_rank, 0),
                                      totalroundroids_growth = t.totalroundroids - COALESCE(a.totalroundroids, 0),
                                      totalroundroids_growth_pc = CASE WHEN (a.totalroundroids != 0) THEN COALESCE((t.totalroundroids - a.totalroundroids) * 100.0 / a.totalroundroids, 0) ELSE 0 END,
                                      totallostroids_growth = t.totallostroids - COALESCE(a.totallostroids, 0),
                                      totallostroids_growth_pc = CASE WHEN (a.totallostroids != 0) THEN COALESCE((t.totallostroids - a.totallostroids) * 100.0 / a.totallostroids, 0) ELSE 0 END,
                                 """ ) +
                                 """
                                      ticksroiding = COALESCE(a.ticksroiding, 0) + CASE WHEN (t.size > a.size) THEN 1 ELSE 0 END,
                                      ticksroided = COALESCE(a.ticksroided, 0) + CASE WHEN (t.size < a.size) THEN 1 ELSE 0 END,
                                      tickroids = COALESCE(a.tickroids, 0) + t.size,
                                      avroids = COALESCE((a.tickroids + t.size) / (a.age + 1.0), t.size),
                                 """ + ((
                                 """
                                      %s_highest_rank = CASE WHEN (t.%s_rank <= COALESCE(a.%s_highest_rank, t.%s_rank)) THEN t.%s_rank ELSE a.%s_highest_rank END,
                                      %s_highest_rank_tick = CASE WHEN (t.%s_rank <= COALESCE(a.%s_highest_rank, t.%s_rank)) THEN :tick ELSE a.%s_highest_rank_tick END,
                                      %s_lowest_rank = CASE WHEN (t.%s_rank >= COALESCE(a.%s_lowest_rank, t.%s_rank)) THEN t.%s_rank ELSE a.%s_lowest_rank END,
                                      %s_lowest_rank_tick = CASE WHEN (t.%s_rank >= COALESCE(a.%s_lowest_rank, t.%s_rank)) THEN :tick ELSE a.%s_lowest_rank_tick END,
                                 """ * 7) % (("size",)*22 + ("members",)*22 + ("score",)*22 + ("points",)*22 + ("size_avg",)*22 + ("score_avg",)*22 + ("points_avg",)*22)) +
                                 """
                                      totalroundroids = t.totalroundroids, totallostroids = t.totallostroids,
                                      totalroundroids_rank = t.totalroundroids_rank, totallostroids_rank = t.totallostroids_rank,
                                      size_rank = t.size_rank, members_rank = t.members_rank, score_rank = t.score_rank, points_rank = t.points_rank,
                                      size_avg_rank = t.size_avg_rank, score_avg_rank = t.score_avg_rank, points_avg_rank = t.points_avg_rank,
                                      sdiff = COALESCE(t.score - a.score, 0),
                                      pdiff = COALESCE(t.points - a.points, 0),
                                      rdiff = COALESCE(t.size - a.size, 0),
                                      mdiff = COALESCE(t.members - a.members, 0),
                                      srankdiff = COALESCE(t.score_rank - a.score_rank, 0),
                                      prankdiff = COALESCE(t.points_rank - a.points_rank, 0),
                                      rrankdiff = COALESCE(t.size_rank - a.size_rank, 0),
                                      mrankdiff = COALESCE(t.members_rank - a.members_rank, 0),
                                      savgdiff = COALESCE(t.score_avg - a.score_avg, 0),
                                      pavgdiff = COALESCE(t.points_avg - a.points_avg, 0),
                                      ravgdiff = COALESCE(t.size_avg - a.size_avg, 0),
                                      savgrankdiff = COALESCE(t.score_avg_rank - a.score_avg_rank, 0),
                                      pavgrankdiff = COALESCE(t.points_avg_rank - a.points_avg_rank, 0),
                                      ravgrankdiff = COALESCE(t.size_avg_rank - a.size_avg_rank, 0),
                                      idle = CASE WHEN ((t.score-a.score) BETWEEN (a.sdiff-1) AND (a.sdiff+1)) THEN 1 + COALESCE(a.idle, 0) ELSE 0 END
                                    FROM (SELECT *,
                                      rank() OVER (ORDER BY totalroundroids DESC) AS totalroundroids_rank,
                                      rank() OVER (ORDER BY totallostroids DESC) AS totallostroids_rank,
                                      rank() OVER (ORDER BY size DESC) AS size_rank,
                                      rank() OVER (ORDER BY points DESC) AS points_rank,
                                      rank() OVER (ORDER BY members DESC) AS members_rank,
                                      rank() OVER (ORDER BY size_avg DESC) AS size_avg_rank,
                                      rank() OVER (ORDER BY score_avg DESC) AS score_avg_rank,
                                      rank() OVER (ORDER BY points_avg DESC) AS points_avg_rank
                                    FROM (SELECT t.*,
                                      COALESCE(a.totalroundroids + (GREATEST(t.size - a.size, 0)), t.size) AS totalroundroids,
                                      COALESCE(a.totallostroids + (GREATEST(a.size - t.size, 0)), 0) AS totallostroids
                                    FROM alliance AS a, alliance_temp AS t
                                      WHERE a.id = t.id AND a.active = :true) AS t) AS t
                                      WHERE a.id = t.id
                                    AND a.active = :true
                                ;""", bindparams=[tick, true]))
    
            t2=time.time()-t1
            excaliburlog("Update alliances from temp and generate ranks in %.3f seconds" % (t2,))
            t1=time.time()
    
    # ########################################################################### #
    # ##################   HISTORY: EVERYTHING BECOMES FINAL   ################## #
    # ########################################################################### #
    
            # Update stats
            session.execute(text("""UPDATE updates SET
                                      clusters  = (SELECT count(*) FROM cluster  WHERE cluster.active  = :true),
                                      galaxies  = (SELECT count(*) FROM galaxy   WHERE galaxy.active   = :true),
                                      planets   = (SELECT count(*) FROM planet   WHERE planet.active   = :true),
                                      alliances = (SELECT count(*) FROM alliance WHERE alliance.active = :true),
                                      c200     = (SELECT count(*) FROM planet WHERE planet.active = :true AND x = 200),
                                      ter      = (SELECT count(*) FROM planet WHERE planet.active = :true AND race ILIKE 'ter%'),
                                      cat      = (SELECT count(*) FROM planet WHERE planet.active = :true AND race ILIKE 'cat%'),
                                      xan      = (SELECT count(*) FROM planet WHERE planet.active = :true AND race ILIKE 'xan%'),
                                      zik      = (SELECT count(*) FROM planet WHERE planet.active = :true AND race ILIKE 'zik%'),
                                      etd      = (SELECT count(*) FROM planet WHERE planet.active = :true AND race ILIKE 'etd%')
                                    WHERE updates.id = :tick
                                ;""", bindparams=[tick, true]))
    
            t2=time.time()-t1
            excaliburlog("Update stats in: %.3f seconds" % (t2,))
            t1=time.time()
    
            # Copy the dumps to their respective history tables
            session.execute(text("INSERT INTO cluster_history SELECT :tick, :hour, :timestamp, * FROM cluster ORDER BY x ASC;", bindparams=[tick, hour, timestamp]))
            session.execute(text("INSERT INTO galaxy_history SELECT :tick, :hour, :timestamp, * FROM galaxy ORDER BY id ASC;", bindparams=[tick, hour, timestamp]))
            session.execute(text("INSERT INTO planet_history SELECT :tick, :hour, :timestamp, * FROM planet ORDER BY id ASC;", bindparams=[tick, hour, timestamp]))
            session.execute(text("INSERT INTO alliance_history SELECT :tick, :hour, :timestamp, * FROM alliance ORDER BY id ASC;", bindparams=[tick, hour, timestamp]))
    
            t2=time.time()-t1
            excaliburlog("History in %.3f seconds" % (t2,))
            t1=time.time()
    
            # Finally we can commit!
            session.commit()
    
            t2=time.time()-t1
            excaliburlog("Final update in %.3f seconds" % (t2,))
            t1=time.time()
    
            break
        except Exception, e:
            excaliburlog("Something random went wrong, sleeping for 15 seconds to hope it improves: %s" % (str(e),), traceback=True)
            session.rollback()
            time.sleep(15)
            continue

    session.close()

    t1=time.time()-t_start
    excaliburlog("Total time taken: %.3f seconds" % (t1,))
    return planet_tick

if __name__ == "__main__":
    bots = []
    prefixes = []
    for config in configs:
        cp = CP()
        cp.optionxform = str
        cp.read(config)
        bots += [cp]
        prefixes += [cp.get("DB", "prefix")]
    
    if len(sys.argv) > 1:
        Config.set("URL", "dumps", sys.argv[1])
    excaliburlog("Dumping from %s" %(Config.get("URL", "dumps"),))
    
    planet_tick = ticker()
    
    penis()
    closereqs(planet_tick)
    parsescans()
    clean_cache()
    
    # Add a newline at the end
    excaliburlog("\n")
