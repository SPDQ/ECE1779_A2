USE `assignment1_ece1779`;

CREATE TABLE `autoscalingconfig` (
    `ascid` bigint(32) NOT NULL AUTO_INCREMENT,
    `cpu_grow` float NOT NULL,
    `cpu_shrink` float NOT NULL,
    `ratio_expand` float NOT NULL,
    `ratio_shrink` float NOT NULL,
    `timestamp` DATETIME NOT NULL,
    PRIMARY KEY (`ascid`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8;
