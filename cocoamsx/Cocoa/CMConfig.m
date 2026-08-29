#import "CMConfig.h"
#include <stdlib.h>

static CMConfig *_shared;

@interface CMConfig ()
@property (nonatomic, copy, readwrite) NSString *machine;
@property (nonatomic, assign, readwrite) NSInteger volume;
@property (nonatomic, assign, readwrite) NSInteger scale;
@property (nonatomic, copy, readwrite) NSString *vdpSync;
@property (nonatomic, assign, readwrite) NSInteger speed;
@property (nonatomic, copy, readwrite) NSString *socketPath;
@property (nonatomic, copy, readwrite) NSString *snapRange;
@property (nonatomic, copy, readwrite) NSString *configPath;
@end

@implementation CMConfig

+ (CMConfig *)sharedConfig
{
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        _shared = [[CMConfig alloc] init];
        [_shared applyDefaults];
        [_shared reload];
    });
    return _shared;
}

- (void)applyDefaults
{
    self.machine = @"MSX2 - C-BIOS";
    self.volume = 75;
    self.scale = 2;
    self.accelerated = YES;
    self.vdpSync = @"60hz";
    self.speed = 100;
    self.socketPath = @"/tmp/cocoamsx.sock";
    self.snapRange = @"c000-dfff";
}

- (NSString *)findConfigPath
{
    const char *env = getenv("COCOAMSX_CONFIG");
    if (env && env[0])
        return [NSString stringWithUTF8String:env];

    NSString *cwd = [[NSFileManager defaultManager] currentDirectoryPath];
    NSString *local = [cwd stringByAppendingPathComponent:@"cocoamsx.json"];
    if ([[NSFileManager defaultManager] fileExistsAtPath:local])
        return local;

    NSString *home = NSHomeDirectory();
    NSString *xdg = [home stringByAppendingPathComponent:@".config/cocoamsx/config.json"];
    if ([[NSFileManager defaultManager] fileExistsAtPath:xdg])
        return xdg;

    return nil;
}

- (void)reload
{
    [self applyDefaults];

    const char *accEnv = getenv("COCOAMSX_ACCELERATED");
    if (accEnv && accEnv[0] == '0')
        self.accelerated = NO;

    const char *sockEnv = getenv("COCOAMSX_SOCKET");
    if (sockEnv && sockEnv[0])
        self.socketPath = [NSString stringWithUTF8String:sockEnv];

    NSString *path = [self findConfigPath];
    self.configPath = path;
    if (!path)
        return;

    NSData *data = [NSData dataWithContentsOfFile:path];
    if (!data)
        return;

    NSError *err = nil;
    id obj = [NSJSONSerialization JSONObjectWithData:data options:0 error:&err];
    if (![obj isKindOfClass:[NSDictionary class]]) {
        NSLog(@"CMConfig: could not parse %@: %@", path, err);
        return;
    }
    NSDictionary *d = obj;

    if ([d[@"machine"] isKindOfClass:[NSString class]])
        self.machine = d[@"machine"];
    if (d[@"volume"])
        self.volume = [d[@"volume"] integerValue];
    if (d[@"scale"])
        self.scale = [d[@"scale"] integerValue];
    if (d[@"accelerated"] != nil && !accEnv)
        self.accelerated = [d[@"accelerated"] boolValue];
    if ([d[@"vdp_sync"] isKindOfClass:[NSString class]])
        self.vdpSync = d[@"vdp_sync"];
    if (d[@"speed"])
        self.speed = [d[@"speed"] integerValue];
    if ([d[@"socket"] isKindOfClass:[NSString class]] && !sockEnv) {
        NSString *sock = d[@"socket"];
        if ([sock hasPrefix:@"/"])
            self.socketPath = sock;
        else
            self.socketPath = [[[NSFileManager defaultManager] currentDirectoryPath]
                               stringByAppendingPathComponent:sock];
    }
    if ([d[@"snap_range"] isKindOfClass:[NSString class]])
        self.snapRange = d[@"snap_range"];

    NSLog(@"CMConfig: loaded %@ (accelerated=%d scale=%ld volume=%ld)",
          path, self.accelerated, (long)self.scale, (long)self.volume);

    if (self.snapRange.length && !getenv("DISASM_SNAP_RANGE"))
        setenv("DISASM_SNAP_RANGE", [self.snapRange UTF8String], 0);
}

- (void)setAcceleratedFromString:(NSString *)onOff
{
    NSString *s = [onOff lowercaseString];
    if ([s isEqualToString:@"on"] || [s isEqualToString:@"true"] || [s isEqualToString:@"1"])
        self.accelerated = YES;
    else if ([s isEqualToString:@"off"] || [s isEqualToString:@"false"] || [s isEqualToString:@"0"])
        self.accelerated = NO;
}

@end
