#!/usr/bin/env python

from __future__ import with_statement

import os
import sys
import errno
from fuse import FUSE, FuseOSError, Operations
import fuse
import json
import stat
import time,q,re,io
import libsonic
import hashlib
from matcher import Matcher

matcher = Matcher()

class SSFSNode():
    def __init__(self):
        self._file_timestamp = int(time.time())
        
    def get(self,overide):
        z = {
            'st_atime'  : self._file_timestamp,
            'st_ctime'  : self._file_timestamp,
            'st_mtime'  : self._file_timestamp,
            'st_uid'    : os.getuid(),
            'st_gid'    : os.getgid()
        }
        z.update(overide)
        return z
        
class SSFSFolder(SSFSNode):
    def get(self):
        return SSFSNode.get(self,{
            'st_mode' : stat.S_IFDIR | 0555,
            'st_nlink': 2,
            'st_size' : 4096,
        })

class SSFSFile(SSFSNode):
    def init(self,size):
        super(File, self).__init__()
        self.size = size
    def get(self):
        return SSFSNode.get(self,{
            'st_mode' : stat.S_IFREG | 0444,
            'st_nlink': 1,
            'st_size' : self.size
        })

class cached_libsonic():
    def __init__(self,url,user,password,port):
        self.subsonic = libsonic.Connection(url,user,password,port=port)
        
    def getIndexes(self):
        return self.subsonic.getIndexes()
    
    def getGenres(self):
        return self.subsonic.getGenres()
    
    def getMusicDirectory(self,id):
        return self.subsonic.getMusicDirectory(id)
    
    def getSongsByGenre(self,genre):
        return self.subsonic.getSongsByGenre(genre)
    
    def getAlbumListByGenre(self,genre):
        return self.subsonic.getAlbumList('byGenre',genre=genre)
    
    def download(selfself,id):
        return self.subsonic.download(id)
    
#@route(matcher=matcher,regex='^/$')
#  global matcher
#        if not matcher.route(self.path,self,'POST'):
#            self.do_404()
class SubsonicFS(Operations):
    root_dirs = ['artists','albums','playlists','genres'];
    cacheArtists = None
    cacheGenres = None
        
    @q
    def __init__(self,root, url,user,password,port):
        self.root = root
        self.subsonic = cached_libsonic(url,user,password,port)
        self._file_timestamp = int(time.time())
        self.init_cache()
        #print json.dumps(self.cacheArtists)
        #sys.exit(0)

    def cache_filename(self,path):
        hash = hashlib.md5(path.encode('utf-8')).hexdigest() #encode('ascii')
        if(not os.path.exists('/tmp/cache/%s'%(hash[:16]))):
            os.mkdir('/tmp/cache/%s'%(hash[:16]))
        return '/tmp/cache/%s/%s'%(hash[:16],hash[16:])
    
    def init_cache(self):
        self.cache={
            'artists':self.subsonic.getIndexes(),
            'genres':self.subsonic.getGenres(),
            'musicdir':{}
        }

    @q
    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    @q
    def getattr(self, path, fh=None):
        #if path in ['/','._.']:
        #    return self.genericDirAttr()
        if re.search('^/artists/([^/]*)/([^/]*)/([^/]*)/([^/]*)$',path):
            f = SSFSFile()
            f.size=self.get_struct(path)['data']['size']
            return f.get()
        else:
            f = SSFSFolder()
            return f.get()

    def make_dir(self,data):
        return {'type':'dir','data':data}
    
    def make_files(self,data):
        return {'type':'file','data':data}
    
    def get_struct(self,path):
        try:
            data=[]
            paths = path.split('/')[1:]
            #print "--- %s => %s ---"%(path,repr(paths))
            
            if paths[0]=='':
                for n in self.root_dirs:
                    data.append({'name' : n})
                return self.make_dir(data)
    
            if paths[0]=='artists':
                return self.get_struct_artists(paths)
            
            if paths[0]=='genres':
                return self.get_struct_genres(paths)
                
            if paths[0]=='albums':
                return self.get_struct_albums(paths)

        except KeyError:
            return []
            
    def get_cache_musicdir(self,id):
        if id not in self.cache['musicdir']:
            self.cache['musicdir'][id] = self.subsonic.getMusicDirectory(id)
        return self.cache['musicdir'][id]
    
    def get_struct_artists(self,paths):
        data=[] 
        if len(paths) == 1:
            for r in self.cache['artists']['indexes']['index']:
                data.append({'name' : r['name']})
            return self.make_dir(data)
        
        artists = [props for props in self.cache['artists']['indexes']['index'] if props['name'] == paths[1]][0]
        if len(paths) == 2:
            for r in artists['artist']:
                data.append({'name' : r['name']})
            return self.make_dir(data)
        
        artist = [props for props in artists['artist'] if props['name'] == paths[2]][0]
        self.get_cache_musicdir(artist['id'])
        if len(paths) == 3:
            for r in self.cache['musicdir'][artist['id']]['directory']['child']:
                data.append({'name' : r['title']})
            return self.make_dir(data)
        
        album = [props for props in self.cache['musicdir'][artist['id']]['directory']['child'] if props['title'] == paths[3]][0]
        
        self.get_cache_musicdir(album['id'])
        if album['id'] not in self.cache['musicdir']:
            self.cache['musicdir'][album['id']] = self.subsonic.getMusicDirectory(artist['id'])
        if len(paths) == 4:
            for r in self.cache['musicdir'][album['id']]['directory']['child']:
                data.append({'name' : "%02d-%s.%s"%(r['track'],r['title'],r['suffix'])})
                #data.append({'name' : "%02d-%s.%s"%(r['track'],r['title'],'nfo')})
            return self.make_files(data)

        if len(paths) == 5:
            title = [props for props in self.cache['musicdir'][album['id']]['directory']['child'] if "%02d-%s.%s"%(props['track'],props['title'],props['suffix']) == paths[4]][0]
            #if title == None:
            #    title = [props for props in self.cache['musicdir'][album['id']]['directory']['child'] if "%02d-%s.%s"%(props['track'],props['title'],'nfo') == paths[4]][0]
            #print json.dumps(title)
            return self.make_files(title)

    def get_struct_genres(self,paths):
        data=[]
        if len(paths) == 1:
            for r in self.cache['genres']['genres']['genre']:
                data.append({'name' : r['value']})
            return data
        if len(paths) == 2:
            data.append({'name' : 'Songs'})
            data.append({'name' : 'Albums'})
            return self.make_dir(data)
        
        if len(paths) == 3:
            if(paths[2]=='Songs'):
                sub1 = self.subsonic.getSongsByGenre(paths[1])
                pass
            if(paths[2]=='Albums'):
                albums = self.subsonic.getAlbumListByGenre(paths[1])
                for r in albums['albumList']['album']:
                    data.append({'name' : "%s - %s"%(r['artist'],r['title'])})
                return self.make_dir(data)
            #print json.dumps(sub1)
            return self.make_dir(data)
            
    def get_struct_albums(self,paths):
        data=[]
        if len(paths) == 1:
            #data.append({'name' : 'Random'})
            #data.append({'name' : 'Newest'})
            #data.append({'name' : 'Highest'})
            #data.append({'name' : 'Frequent'})
            #data.append({'name' : 'Recent'})
            #data.append({'name' : 'Year'})
            data.append({'name' : 'Genres'})
            return self.make_dir(data)
        
        if len(paths) == 3:
            sub1 = self.subsonic.getSongsByGenre(paths[1])
            if(paths[2]=='Songs'):
                pass
            if(paths[2]=='Albums'):
                pass
                #sub1 = self.subsonic.getAlbumsByGenre(paths[1])
            #print json.dumps(sub1)
            return self.make_dir(data)
            
    @q
    def readdir(self, path, fh):
        yield '.'
        yield '..'
        datas = self.get_struct(path)
        if datas == None:
            return
        for n in datas['data']:
            yield n['name']

    @q
    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    @q
    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def access(self, path, mode):
        pass
    
    def chmod(self, path, mode):
        return False

    def chown(self, path, uid, gid):
        return False

    def mknod(self, path, mode, dev):
        return False

    def rmdir(self, path):
        return False

    def mkdir(self, path, mode):
        return False

    def unlink(self, path):
        return False

    def symlink(self, name, target):
        return False

    def rename(self, old, new):
        return False

    def link(self, target, name):
        return False

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    @q
    def open(self, path, flags):
        access_flags = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if flags & access_flags != os.O_RDONLY:
            return -errno.EACCES
        else:
            cache_filename = self.cache_filename(path);
            if not os.path.exists(cache_filename):
                with io.open(cache_filename,'bw')  as file:
                    data = self.get_struct(path)
                    content = self.subsonic.download(data['data']['id'])
                    file.write(content.read())
            return 128

    @q
    def read(self, path, length, offset, fh):
        with io.open(self.cache_filename(path),'br') as file:
            content = file.read()
        print "-- %s %d--"%(path,len(content))
        if offset < len(content):
            if offset + length > len(content):
                size = len(content) - offset
            return content[offset:offset+size]
        else:
            return ''

    def create(self, path, mode, fi=None):
        return False
    
    def write(self, path, buf, offset, fh):
        return False

    def truncate(self, path, length, fh=None):
        return False

    def flush(self, path, fh):
        return True

    def release(self, path, fh):
        return True

    def fsync(self, path, fdatasync, fh):
        #return self.flush(path, fh)
        return True

def main(mountpoint,url,user,password,port):
    pid = str(os.getpid())
    f = open('/tmp/subsonic_pid', 'w')
    f.write(pid)
    f.close()
    
    # python subsonicfs.py  /tmp/fs http://xxxxxx.xxxxx.com user password 80
    FUSE(SubsonicFS('/tmp',url,user,password,port), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
