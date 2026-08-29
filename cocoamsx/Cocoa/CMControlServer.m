#import "CMControlServer.h"
#import "CMConfig.h"
#import "CMEmulatorController.h"
#import "CMKeyboardManager.h"
#import "CMMsxDisplayView.h"

#ifdef DISASMTRACE
#include "../Src/Debugger/disasmtrace.h"
#endif

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

static CMControlServer *_ctl;

@implementation CMControlServer
{
    CMEmulatorController *emulator;
    int listenFd;
    BOOL running;
}

+ (CMControlServer *)sharedServer
{
    static dispatch_once_t once;
    dispatch_once(&once, ^{ _ctl = [[CMControlServer alloc] init]; });
    return _ctl;
}

- (NSInteger)keyCodeForName:(NSString *)name
{
    static NSDictionary *map;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        map = @{
            @"up": @126, @"down": @125, @"left": @123, @"right": @124,
            @"space": @49, @"shift": @56, @"ctrl": @59, @"alt": @58,
            @"z": @6, @"x": @7, @"a": @0, @"s": @1, @"enter": @36,
            @"esc": @53, @"tab": @48, @"f8": @100, @"f9": @101
        };
    });
    NSString *k = [[name lowercaseString] stringByTrimmingCharactersInSet:
                   [NSCharacterSet whitespaceCharacterSet]];
    NSNumber *n = map[k];
    if (n) return [n integerValue];
    unsigned v = 0;
    if ([k hasPrefix:@"0x"] && sscanf(k.UTF8String, "%x", &v) == 1)
        return (NSInteger)v;
    return -1;
}

- (NSString *)handleLine:(NSString *)line
{
    NSArray *tok = [line componentsSeparatedByCharactersInSet:
                    [NSCharacterSet whitespaceCharacterSet]];
    NSMutableArray *parts = [NSMutableArray array];
    for (NSString *t in tok) {
        if (t.length) [parts addObject:t];
    }
    if (parts.count == 0)
        return @"err empty";

    NSString *cmd = [parts[0] lowercaseString];

    if ([cmd isEqualToString:@"ping"])
        return @"ok pong";

    if ([cmd isEqualToString:@"reload-config"]) {
        [[CMConfig sharedConfig] reload];
        [self applyLiveConfig];
        return @"ok";
    }

    if ([cmd isEqualToString:@"accelerated"] && parts.count >= 2) {
        [[CMConfig sharedConfig] setAcceleratedFromString:parts[1]];
        dispatch_sync(dispatch_get_main_queue(), ^{
            [emulator.screen setAccelerated:[CMConfig sharedConfig].accelerated];
        });
        return [CMConfig sharedConfig].accelerated ? @"ok on" : @"ok off";
    }

    if ([cmd isEqualToString:@"pause"]) {
        dispatch_sync(dispatch_get_main_queue(), ^{ [emulator pause]; });
        return @"ok";
    }
    if ([cmd isEqualToString:@"resume"]) {
        dispatch_sync(dispatch_get_main_queue(), ^{ [emulator resume]; });
        return @"ok";
    }

    if ([cmd isEqualToString:@"snap"]) {
#ifdef DISASMTRACE
        disasmTraceRequestSnapshot();
        return @"ok";
#else
        return @"err no DISASMTRACE";
#endif
    }
    if ([cmd isEqualToString:@"autosnap"] && parts.count >= 2) {
#ifdef DISASMTRACE
        BOOL want = [[parts[1] lowercaseString] isEqualToString:@"on"];
        if (want != (BOOL)disasmTraceAutoSnapActive())
            disasmTraceToggleAutoSnap();
        return disasmTraceAutoSnapActive() ? @"ok on" : @"ok off";
#else
        return @"err no DISASMTRACE";
#endif
    }

    if ([cmd isEqualToString:@"watch"] && parts.count >= 2) {
#ifdef DISASMTRACE
        disasmTraceSetWatch([parts[1] UTF8String]);
        return @"ok";
#else
        return @"err no DISASMTRACE";
#endif
    }
    if ([cmd isEqualToString:@"exec"] && parts.count >= 2) {
#ifdef DISASMTRACE
        disasmTraceSetExec([parts[1] UTF8String]);
        return @"ok";
#else
        return @"err no DISASMTRACE";
#endif
    }

    if ([cmd isEqualToString:@"peek"] && parts.count >= 2) {
#ifdef DISASMTRACE
        unsigned addr = 0;
        if (sscanf([parts[1] UTF8String], "%x", &addr) != 1)
            return @"err bad addr";
        UInt8 b = 0;
        if (disasmTracePeekRange((UInt16)addr, 1, &b, 2000) != 0)
            return @"err timeout";
        return [NSString stringWithFormat:@"ok %02x", b];
#else
        return @"err no DISASMTRACE";
#endif
    }

    if ([cmd isEqualToString:@"dump"] && parts.count >= 3) {
#ifdef DISASMTRACE
        unsigned addr = 0, len = 0;
        if (sscanf([parts[1] UTF8String], "%x", &addr) != 1)
            return @"err bad addr";
        if (sscanf([parts[2] UTF8String], "%x", &len) != 1)
            sscanf([parts[2] UTF8String], "%u", &len);
        if (len == 0 || len > 4096)
            return @"err bad len";
        UInt8 buf[4096];
        if (disasmTracePeekRange((UInt16)addr, (UInt16)len, buf, 2000) != 0)
            return @"err timeout";
        NSMutableString *s = [NSMutableString stringWithString:@"ok"];
        unsigned i;
        for (i = 0; i < len; i++)
            [s appendFormat:@" %02x", buf[i]];
        return s;
#else
        return @"err no DISASMTRACE";
#endif
    }

    if ([cmd isEqualToString:@"wait"] && parts.count >= 4) {
#ifdef DISASMTRACE
        unsigned addr = 0, val = 0;
        if (sscanf([parts[1] UTF8String], "%x", &addr) != 1)
            return @"err bad addr";
        if (![parts[2] isEqualToString:@"=="])
            return @"err only == supported";
        if (sscanf([parts[3] UTF8String], "%x", &val) != 1)
            return @"err bad value";
        int timeout = 30000;
        if (parts.count >= 5)
            timeout = [parts[4] intValue];
        if (disasmTraceWaitEquals((UInt16)addr, (UInt8)val, timeout) != 0)
            return @"err timeout";
        return @"ok";
#else
        return @"err no DISASMTRACE";
#endif
    }

    if ([cmd isEqualToString:@"key"] && parts.count >= 3) {
        NSInteger kc = [self keyCodeForName:parts[2]];
        if (kc < 0) return @"err unknown key";
        BOOL down = [[parts[1] lowercaseString] isEqualToString:@"down"];
        dispatch_sync(dispatch_get_main_queue(), ^{
            [[CMKeyboardManager sharedInstance] injectKeyCode:kc isDown:down];
        });
        return @"ok";
    }

    if ([cmd isEqualToString:@"hold"] && parts.count >= 3) {
        NSInteger kc = [self keyCodeForName:parts[1]];
        if (kc < 0) return @"err unknown key";
        int frames = [parts[2] intValue];
        if (frames < 1) frames = 1;
        dispatch_sync(dispatch_get_main_queue(), ^{
            [[CMKeyboardManager sharedInstance] injectKeyCode:kc isDown:YES];
        });
        usleep((useconds_t)frames * 16667);
        dispatch_sync(dispatch_get_main_queue(), ^{
            [[CMKeyboardManager sharedInstance] injectKeyCode:kc isDown:NO];
        });
        return @"ok";
    }

    if ([cmd isEqualToString:@"savestate"] && parts.count >= 2) {
        NSString *path = parts[1];
        __block BOOL ok = NO;
        dispatch_sync(dispatch_get_main_queue(), ^{
            ok = [emulator saveStateToFile:path];
        });
        return ok ? @"ok" : @"err save failed";
    }

    if ([cmd isEqualToString:@"loadstate"] && parts.count >= 2) {
        NSString *path = parts[1];
        if (![[NSFileManager defaultManager] fileExistsAtPath:path])
            return @"err no such file";
        dispatch_sync(dispatch_get_main_queue(), ^{
            [emulator startWithState:path];
        });
        return @"ok";
    }

    if ([cmd isEqualToString:@"screenshot"] && parts.count >= 2) {
        NSString *path = parts[1];
        __block BOOL ok = NO;
        dispatch_sync(dispatch_get_main_queue(), ^{
            NSImage *img = [emulator.screen captureScreen:NO];
            NSData *png = nil;
            for (NSImageRep *rep in img.representations) {
                if ([rep isKindOfClass:[NSBitmapImageRep class]]) {
                    png = [(NSBitmapImageRep *)rep representationUsingType:NSBitmapImageFileTypePNG
                                                               properties:@{}];
                    break;
                }
            }
            ok = png && [png writeToFile:path atomically:YES];
        });
        return ok ? @"ok" : @"err screenshot failed";
    }

    return [NSString stringWithFormat:@"err unknown %@", cmd];
}

- (void)applyLiveConfig
{
    dispatch_async(dispatch_get_main_queue(), ^{
        [emulator applyLiveConfig];
    });
}

- (void)serveClient:(int)fd
{
    char buf[4096];
    NSMutableData *acc = [NSMutableData data];
    for (;;) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n <= 0)
            break;
        [acc appendBytes:buf length:(NSUInteger)n];
        for (;;) {
            NSData *nl = [acc subdataWithRange:NSMakeRange(0, acc.length)];
            const char *p = memchr(nl.bytes, '\n', nl.length);
            if (!p) break;
            NSUInteger idx = (NSUInteger)(p - (const char *)nl.bytes);
            NSData *lineData = [acc subdataWithRange:NSMakeRange(0, idx)];
            [acc replaceBytesInRange:NSMakeRange(0, idx + 1) withBytes:NULL length:0];
            NSString *line = [[NSString alloc] initWithData:lineData encoding:NSUTF8StringEncoding];
            if (!line) continue;
            NSString *reply = [self handleLine:[line stringByTrimmingCharactersInSet:
                                                [NSCharacterSet whitespaceAndNewlineCharacterSet]]];
            NSString *out = [reply stringByAppendingString:@"\n"];
            const char *bytes = [out UTF8String];
            write(fd, bytes, strlen(bytes));
        }
    }
    close(fd);
}

- (void)listenLoop:(NSString *)path
{
    unlink([path UTF8String]);
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
        NSLog(@"CMControlServer: socket failed");
        return;
    }
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, [path UTF8String], sizeof(addr.sun_path) - 1);
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        NSLog(@"CMControlServer: bind %s failed", addr.sun_path);
        close(fd);
        return;
    }
    listen(fd, 4);
    listenFd = fd;
    NSLog(@"CMControlServer: listening on %@", path);

    while (running) {
        int cfd = accept(fd, NULL, NULL);
        if (cfd < 0) {
            if (!running) break;
            continue;
        }
        [self serveClient:cfd];
    }
    close(fd);
    unlink([path UTF8String]);
}

- (void)startWithEmulator:(CMEmulatorController *)emu
{
    emulator = emu;
    if (running)
        return;
    running = YES;
    listenFd = -1;
    NSString *path = [CMConfig sharedConfig].socketPath;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        [self listenLoop:path];
    });
}

- (void)stop
{
    running = NO;
    if (listenFd >= 0) {
        close(listenFd);
        listenFd = -1;
    }
}

@end
