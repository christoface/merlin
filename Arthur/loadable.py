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
 
from datetime import datetime, timedelta
from random import randrange

from Core.exceptions_ import LoadableError, UserError
from Core.config import Config
from Core.db import Session, session
from Core.maps import User, Arthur, PageView
from Core.loadable import _base, require_user, require_planet
from Arthur.context import render

SESSION_KEY = "SESSION"
LOGOUT = "/logout/"
USER = "username"
PASS = "password"

# ########################################################################### #
# ##############################    LOADABLE    ############################# #
# ########################################################################### #

class loadable(_base):
    
    def __new__(cls):
        self = super(loadable, cls).__new__(cls)
        self.name = cls.__name__
        
        if cls.access in Config.options("Access"):
            self.access = Config.getint("Access", cls.access)
        elif type(cls.access) in (int, type(None),):
            self.access = cls.access
        else:
            raise LoadableError("Invalid access level")
        
        return self
    
    def __call__(self, request, **kwargs):
        return self.run(request, **kwargs)
    
    def authenticate(self, request):
        request.session = None
        key = request.COOKIES.get(SESSION_KEY)
        if key:
            auth = Arthur.load(key, datetime.now())
            if auth is None:
                raise UserError("Your session has expired, please login again.")
            if request.path == LOGOUT:
                session.delete(auth)
                session.commit()
                raise UserError("Logged out.")
            request.session = auth
            return auth.user, None
        elif (request.REQUEST.get(USER) and request.REQUEST.get(PASS)):
            user = User.load(name=request.REQUEST.get(USER), passwd=request.REQUEST.get(PASS))
            if user is None:
                raise UserError("Invalid user.")
            else:
                key = self.generate_key(user)
                auth = Arthur(key=key, expire=datetime.now()+timedelta(days=1), user=user)
                session.query(Arthur).filter(Arthur.user == user).delete()
                session.add(auth)
                session.commit()
                request.session = auth
                return user, key
        else:
            return None, None
    
    def router(self, request):
        user, cookie = self.authenticate(request)
        user = self.check_access(user)
        return user, cookie
    
    def run(self, request, **kwargs):
        try:
            user, cookie = self.router(request)
            response = self.execute(request, user, **kwargs)
            
            session = Session()
            session.add(PageView(page = self.name,
                                 full_request = request.get_full_path(),
                                 username = user.name,
                                 session = request.session.key,
                                 hostname = request.get_host(),))
            session.commit()
            
            if cookie is not None:
                response.set_cookie(SESSION_KEY, cookie, expires=request.session.expire)
            
            return response
        
        except UserError, e:
            return self.login_page(request, str(e))
    
    def execute(self, request, user, **kwargs):
        pass
    
    def check_access(self, user):
        user = user or User()
        if not Config.getboolean("Arthur", "public") and not self.is_user(user):
            raise UserError("Hi! Please login below:")
        if user.access >= self.access:
            return user
        else:
            raise UserError("You don't have access to this page")
    
    def login_page(self, request, msg):
        response = render("login.tpl", request, msg=msg)
        response.delete_cookie(SESSION_KEY)
        return response
    
    def generate_key(self, user):
        return User.hasher(user.name+user.passwd+str(datetime.now())+str(randrange(1,1000000000)))

def load(hook):
    return hook()
