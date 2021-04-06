CREATE DATABASE IF NOT EXISTS `assignment1_ece1779` DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;
USE `assignment1_ece1779`;

CREATE TABLE IF NOT EXISTS `users` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `username` varchar(50) NOT NULL,
    `password` varchar(255) NOT NULL,
    `email` varchar(100),
    `admin` BOOLEAN,
    PRIMARY KEY (`id`)
    ) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `images` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `user_id` int NOT NULL,
    `image_path` varchar(255) NOT NULL,
    `image_type` varchar(255) NOT NULL,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`user_id`) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8;

INSERT INTO `users` (`id`, `username`, `password`, `email`, `admin`) VALUES (1, 'admin', 'pbkdf2:sha256:150000$LcMw2gg3$c9dedb1034a04d74ce9f9f0cf5ab64ceefa04a8665e2d20183756e289e10aaeb', 'test@gmail.com', true);
